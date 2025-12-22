import logging
import os
import subprocess
import traceback
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Exists, Count, Subquery, OuterRef
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_GET
from django_q.tasks import fetch

from accounts.caches import DepartmentCache
from common.decorators import json_login_required
from common.mixins import JsonLoginRequiredMixin
from common.utils import RequestUtils, ResponseUtils
from meetings.forms import MeetingForm
from meetings.models import Meeting, Attendee, MeetingTypeCode, Recording, Segment, SpeechRecognition, Summarization, Word
from reservations.models import Reservation

logger = logging.getLogger(__name__)
size = 10


@login_required(login_url='sign-in')
def meetings(request):
    page = RequestUtils.get_page(request)
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    user = request.GET.get('user')
    attendee = request.GET.get('attendee')
    word_search_type = request.GET.get('word_search_type')
    word = request.GET.get('word')

    q = Q(is_active=True)
    if start_date:
        q &= Q(start_datetime__gte=start_date)
    if end_date:
        q &= Q(start_datetime__lt=end_date)
    if user:
        q &= Q(created_user__username__icontains=user)
    if attendee:
        q &= Exists(
            Reservation.attendees.through.objects.filter(
                reservation_id=OuterRef('id'),
                user__username__icontains=attendee
            )
        )
    if word:
        if word_search_type == 'start':
            search_content_like = Q(search_content__istartswith=word)
        elif word_search_type == 'end':
            search_content_like = Q(search_content__iendswith=word)
        else:
            search_content_like = Q(search_content__icontains=word)

        q &= Exists(
            Word.objects.filter(
                search_content_like,
                segment__speech_recognition__recording__meeting_id=OuterRef('pk')
            )
        )

    active_meetings = \
        (Meeting.objects
         .select_related('reservation')
         .select_related('created_user')
         .prefetch_related('attendees')
         .only('id', 'type', 'reservation__id', 'reservation__room__name', 'title', 'created_user__username', 'start_datetime', 'end_datetime', 'is_open')
         .annotate(
            group_name=Subquery(
                Group.objects.filter(user__id=OuterRef('created_user_id'))
                .order_by('id')
                .values('name')[:1]
            ),
            exist_recording=Exists(
                Recording.objects.filter(meeting_id=OuterRef('pk'))
            ),
            attendees_count=Count('attendees')
        )
         .filter(q)
         .order_by('-start_datetime', '-id'))

    paginator = Paginator(active_meetings, size)
    page_meetings = paginator.get_page(page)

    for r in page_meetings:
        r.attendees_names = ", ".join([a.username for a in r.attendees.all()])
        r.editable = r.can_edit(request.user)
        r.viewable = r.can_view(request.user, r.editable)

    return render(request, 'meetings/meetings.html', {'page_meetings': page_meetings})


class MeetingView(LoginRequiredMixin, View):
    meeting_form_class = MeetingForm
    template_name = 'meetings/meeting.html'

    def get(self, request, *args, **kwargs):
        pk = kwargs['pk']
        if pk == 0:
            return render(request, self.template_name, {'form': self.meeting_form_class(readonly=False), 'departments': DepartmentCache.find(is_active=True)})

        meeting = get_object_or_404(Meeting, pk=pk)

        editable = meeting.can_edit(request.user)
        viewable = meeting.can_view(request.user, editable)

        if not viewable:
            messages.error(request, "⛔️ 조회 권한이 없어요.\n(리더, 작성자, 참석자만 조회할 수 있어요.)")
            return redirect('meetings')

        attendees = [attendee.user.pk for attendee in Attendee.objects.select_related('user').prefetch_related("user__groups").filter(meeting=meeting).all()]

        recordings = Recording.objects.filter(
            meeting=meeting
        ).select_related(
            'latest_speech_recognition',
            'latest_summarization'
        ).filter(
            is_active=True
        ).only(
            'id', 'webm_file', 'webm_file_size', 'play_millisecond', 'latest_speech_recognition__id', 'latest_speech_recognition__task_status_code',
            'latest_summarization__id', 'latest_summarization__task_status_code',
        ).order_by('id')

        return render(
            request,
            self.template_name,
            {
                'form': self.meeting_form_class(instance=meeting, readonly=not editable),
                'attendees': attendees,
                'recordings': recordings,
                'departments': DepartmentCache.find(is_active=True),
            })

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        pk = kwargs['pk']
        if pk != 0:
            reservation = get_object_or_404(Reservation, pk=pk)
            saved_meeting = Meeting.objects.filter(reservation=reservation, is_active=True).first()
            if saved_meeting:
                return redirect('meeting', pk=saved_meeting.pk)

            meeting = Meeting.objects.create(
                type=MeetingTypeCode.RESERVATION,
                reservation=reservation,
                title=reservation.title,
                start_datetime=reservation.start_datetime,
                end_datetime=reservation.end_datetime,
                created_user_id=request.user.pk,
                last_modified_user_id=request.user.pk,
            )
            meeting.save()
            attendees = set([r.user_id for r in reservation.reservation_attendee_set.all()])
            meeting.save_attendees(attendees, request.user)
            messages.success(request, '👍 회의가 시작되었어요.')
            return redirect('meeting', pk=meeting.pk)

        form = self.meeting_form_class(request.POST)
        attendees = set(request.POST.getlist("attendees"))
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.created_user_id = request.user.pk
            meeting.last_modified_user_id = request.user.pk
            meeting.save()
            meeting.save_attendees(attendees, request.user)

            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({
                    'status': 'success',
                    'meeting_id': meeting.pk,
                    'message': '👍 회의가 등록되었어요.'
                })

            messages.success(request, '👍 회의가 등록되었어요.')
            return redirect('meetings')

        return self._error(request, form, attendees)

    @transaction.atomic
    def put(self, request, *args, **kwargs):
        pk = kwargs['pk']
        meeting = get_object_or_404(Meeting.objects.prefetch_related('attendees'), pk=pk)

        editable = meeting.can_edit(request.user)

        if not editable:
            messages.error(request, "⛔️ 수정 권한이 없어요.\n(리더, 작성자, 참석자만 수정할 수 있어요.)")
            return redirect('meetings')

        form = self.meeting_form_class(request.POST, instance=meeting)
        attendees = set(map(int, request.POST.getlist("attendees")))
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.last_modified_user_id = request.user.pk
            meeting.last_modified_date = timezone.now()
            update_fields = ['title', 'memo', 'start_datetime', 'end_datetime', 'is_open', 'last_modified_user_id', 'last_modified_date']
            meeting.save(update_fields=update_fields)
            meeting.save_attendees(attendees, request.user)
            messages.success(request, "👌 회의가 수정되었어요.")
            return redirect('meetings')

        return self._error(request, form, attendees)

    def delete(self, request, *args, **kwargs):
        meeting = get_object_or_404(Meeting, pk=kwargs['pk'])

        editable = meeting.can_edit(request.user)

        if not editable:
            messages.error(request, "⛔️ 삭제 권한이 없어요.\n(리더, 작성자, 참석자만 삭제할 수 있어요.)")
            return redirect('meetings')

        meeting.is_active = False
        meeting.last_modified_user_id = request.user.pk
        meeting.last_modified_date = timezone.now()
        update_fields = ['is_active', 'last_modified_user_id', 'last_modified_date']
        meeting.save(update_fields=update_fields)
        messages.success(request, '👋 회의가 삭제되었어요.')
        return redirect('meetings')

    def _get_error_message(self, form: MeetingForm):
        errors = []
        for field_name, field_errors in form.errors.items():
            if field_name == '__all__':
                errors.extend(field_errors)
            else:
                field_label = form.fields[field_name].label or field_name
                for error in field_errors:
                    errors.append(f"{field_label}은(는) {error}")
        if errors:
            return "\n".join(list(set(errors)))
        return None

    def _error(self, request, form: MeetingForm, attendees) -> HttpResponse:
        error_message = self._get_error_message(form)
        print(error_message)

        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({
                'status': 'error',
                'message': error_message if error_message else '⛔️ 입력값을 확인해 주세요.',
                'errors': form.errors
            }, status=400)

        if error_message:
            messages.warning(request, error_message)
        return render(request, self.template_name, {'form': form, 'attendees': [int(u) for u in attendees], 'departments': DepartmentCache.find(is_active=True)})


REQUIRES_CONVERSION_EXTENSIONS = ['.wav', '.mp3', '.m4a', '.ogg', '.flac']


class RecordingUploadView(JsonLoginRequiredMixin, View):
    def post(self, request, meeting_id):
        meeting = get_object_or_404(Meeting, pk=meeting_id)

        editable = meeting.can_edit(request.user)

        if not editable:
            return JsonResponse({'status': 'error', 'message': '⛔️ 삭제 권한이 없어요.\n(리더, 작성자, 참석자만 삭제할 수 있어요.'}, status=403)

        file = request.FILES.get('file')
        if not file:
            return JsonResponse({'status': 'error', 'message': '⛔️ 녹음 또는 파일을 업로드해 주세요.'}, status=400)

        original_file_name_with_ext = file.name
        _, file_ext = os.path.splitext(file.name)
        uuid_file_name = str(uuid.uuid4())
        webm_file_name = f"{uuid_file_name}.webm"
        upload_file_name = f"{uuid_file_name}.{file_ext.lower()}"
        file_ext = file_ext.lower()
        source_type = request.POST.get('source_type', 'unknown')

        recording_fields = {
            'meeting': meeting,
            'content_type': file.content_type or '',
            'upload_file_name': original_file_name_with_ext,
            'created_user': request.user,
            'last_modified_user': request.user,
        }

        is_webm_file = (file_ext == '.webm' or file.content_type == 'audio/webm')

        if is_webm_file:
            file.name = webm_file_name
            recording_fields['webm_file'] = file
            recording_fields['webm_file_size'] = file.size

            recording_fields['upload_file'] = None
            recording_fields['upload_file_size'] = 0
        elif source_type == 'upload_file' and file_ext in REQUIRES_CONVERSION_EXTENSIONS:
            file.name = upload_file_name
            recording_fields['upload_file'] = file
            recording_fields['upload_file_size'] = file.size

            temp_input_path = None
            temp_output_path = None

            try:
                temp_input_path = os.path.join(settings.MEDIA_ROOT, 'temp', upload_file_name)
                temp_output_path = os.path.join(settings.MEDIA_ROOT, 'temp', webm_file_name)
                os.makedirs(os.path.dirname(temp_input_path), exist_ok=True)

                with open(temp_input_path, 'wb') as temp_file:
                    for chunk in file.chunks():
                        temp_file.write(chunk)

                command = [
                    'ffmpeg',
                    '-i', temp_input_path,  # -i: 입력 파일
                    '-c:a', 'libopus',  # -c:a: 오디오 코덱 (Opus는 WebM에서 효율적이며 품질이 좋음)
                    '-b:a', '128k',  # -b:a: 오디오 비트레이트 (예: 128k)
                    '-vn',  # -vn: 비디오 트랙 제거 (오디오 파일이므로)
                    '-y',  # 덮어쓰기 허용
                    '-f', 'webm',
                    '-cluster_size_limit', '0',  # 클러스터 크기 제한 해제 (더 작은 클러스터 생성 유도)
                    # '-chunk_limit', '500000',  # 클러스터 당 최대 청크 크기 제한 (더 잦은 Cues 생성 유도)
                    '-fflags', '+genpts',  # 타임스탬프 생성을 강제
                    '-movflags', 'faststart',  # 스트리밍 및 시킹 최적화 (메타데이터를 파일 시작으로 이동)
                    temp_output_path
                ]
                subprocess.run(command, check=True, capture_output=True)

                with open(temp_output_path, 'rb') as converted_file:
                    converted_data = converted_file.read()

                webm_content = ContentFile(converted_data)
                webm_content.name = webm_file_name

                recording_fields['webm_file'] = webm_content
                recording_fields['webm_file_size'] = len(converted_data)

                logger.info(f"Successfully converted {file.name} to WebM.")
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg conversion failed: {e.stderr.decode()}")
                return JsonResponse({'status': 'error', 'message': '😱 파일 변환에 실패했어요.'}, status=500)
            except Exception as e:
                logger.error(f"File conversion failed: {e}")
                return JsonResponse({'status': 'error', 'message': '😱 파일 변환 중 시스템 예외가 발생했어요.'}, status=500)
            finally:
                if temp_input_path and os.path.exists(temp_input_path):
                    os.remove(temp_input_path)
                if temp_output_path and os.path.exists(temp_output_path):
                    os.remove(temp_output_path)

        else:
            return JsonResponse({'status': 'error', 'message': '⛔️ 유효한 파일을 업로드해 주세요.'}, status=400)

        with transaction.atomic():
            recording = Recording.objects.create(**recording_fields)

        download_url = reverse('recording_download', args=[meeting_id, recording.pk])

        return JsonResponse({
            'status': 'success',
            'id': recording.pk,
            'play_millisecond': recording.play_millisecond,  # 실제 재생 시간 추출 로직 필요
            'download_url': request.build_absolute_uri(download_url) if download_url else None,
        })


class RecordingDownloadView(JsonLoginRequiredMixin, View):
    def get(self, request, meeting_id, recording_id):
        try:
            recording = Recording.objects.select_related('meeting').get(pk=recording_id, meeting_id=meeting_id)
        except Recording.DoesNotExist:
            return HttpResponse('🚫 녹음 정보를 찾을 수 없어요.', status=400)

        if not recording.meeting.can_view(request.user):
            return HttpResponseForbidden("⛔️ 접근 권한이 없어요.")

        file_field = recording.upload_file if recording.upload_file else recording.webm_file
        if not file_field:
            return HttpResponse('😱 파일 경로가 지정되지 않았어요.', status=404)

        file_path = file_field.path
        file_size = file_field.size

        if not os.path.exists(file_path):
            return HttpResponse('😱 파일이 서버에 존재하지 않아요.', status=404)

        file_name = recording.upload_file_name

        return ResponseUtils.response_file_with_range(
            request,
            recording.content_type,
            file_path,
            file_size,
            file_name if request.GET.get('mode') != 'play' else None
        )


class RecordingView(JsonLoginRequiredMixin, View):
    def get(self, request, meeting_id, recording_id):
        try:
            recording = Recording.find_by_id_with_latest_tasks(recording_id)
            speech_recognition = recording.latest_speech_recognition
            summarization = recording.latest_summarization

            segment_queryset = (Segment.objects
                                .select_related('speaker')
                                .only('id', 'speaker__user', 'speaker__speaker_label', 'start_millisecond', 'end_millisecond', 'text', 'corrected_text')
                                .filter(speech_recognition=speech_recognition)
                                .all())

            segments = []

            for segment in segment_queryset:
                segments.append({
                    'id': segment.id,
                    'speaker': segment.speaker.user.username if segment.speaker.user else segment.speaker.speaker_label,
                    'start': segment.start_millisecond,
                    'end': segment.end_millisecond,
                    'text': segment.text,
                    'corrected_text': segment.corrected_text,
                })

            return JsonResponse({
                'status': 'success',
                'recording_id': recording_id,
                'info': {
                    'speech_recognition_model_name': speech_recognition.speech_recognition_model_name,
                    'align_model_name': speech_recognition.align_model_name,
                    'diarization_model_name': speech_recognition.diarization_model_name,
                    'language_code': speech_recognition.language_code,
                    'generative_ai_model_name': summarization.generative_ai_model_name,
                },
                'segments': segments,
                'summarization_content': summarization.summarization_content,
                'minutes_content': summarization.minutes_content,
                'action_items': summarization.action_items,
            })
        except Exception as e:
            logger.error(f"회의 기록 조회 중 예외 발생: {e}")
            return JsonResponse({'status': 'error', 'message': '😱 회의 기록을 조회하는 중 시스템 예외가 발생했어요.'}, status=500)

    def put(self, request, meeting_id, recording_id):
        user = request.user

        try:
            recording = Recording.find_by_id_with_latest_tasks(recording_id)
            if not recording.is_active:
                raise Recording.DoesNotExist()

            if recording.can_speech_recognition_task():
                recording.start_speech_recognition_task(user)

                return JsonResponse({
                    'status': recording.latest_speech_recognition.task_status_code,
                    'task_id': recording.latest_speech_recognition.task_id,
                    'message': f'🛠️ 전사 작업을 시작했어요. 예상 소요 시간: 약 {recording.latest_speech_recognition.get_estimated_minute()}분.'
                })

            if recording.is_processing_speech_recognition():
                return JsonResponse({
                    'status': recording.latest_speech_recognition.task_status_code,
                    'task_id': recording.latest_speech_recognition.task_id,
                    'message': f"🛠️ 전사 작업 {recording.latest_speech_recognition.get_task_status()}을(를) 하고 있어요. 예상 소요 시간: 약 {recording.latest_speech_recognition.get_remaining_estimated_minute()}분"
                })

            if recording.latest_speech_recognition.can_summarization_task():
                summarization = recording.latest_speech_recognition.start_summarization_task(user)

                return JsonResponse({
                    'status': summarization.task_status_code,
                    'task_id': summarization.task_id,
                    'message': f'🛠️ 교정·요약 작업을 시작했어요. 예상 소요 시간: 약 {summarization.get_estimated_minute()}분'
                })

            if recording.latest_summarization.is_processing():
                return JsonResponse({
                    'status': recording.latest_summarization.task_status_code,
                    'task_id': recording.latest_summarization.task_id,
                    'message': f"🛠‍ 교정·요약 작업을 하고 있어요. 예상 소요 시간: 약 {recording.latest_summarization.get_remaining_estimated_minute()}분"
                })

            return JsonResponse({
                'status': 'completed',
                'recording_id': recording_id,
                'speech_recognition_id': recording.latest_speech_recognition.id,
                'summarization_id': recording.latest_summarization.id,
                'message': f"👍 전사 및 교정·요약 작업이 완료되었어요. 소요 시간: 약 {recording.latest_speech_recognition.get_task_minute() + recording.latest_summarization.get_task_minute()}분",
            })
        except Recording.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '😱 녹음 정보를 확인할 수 없어요.'}, status=404)
        except Exception as e:
            traceback.print_exc()
            logger.error(f"음성 텍스트 변환 중 예외 발생: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class RecordingTaskView(JsonLoginRequiredMixin, View):
    def get(self, request, meeting_id, recording_id, task_id):
        try:
            recording = Recording.find_by_id_with_latest_tasks(recording_id)
            if not recording.is_active:
                raise Recording.DoesNotExist()
            speech_recognition = recording.latest_speech_recognition
            if speech_recognition is None:
                raise SpeechRecognition.DoesNotExist()

            task = fetch(task_id)

            if task:
                if task.success:
                    if isinstance(task.result, dict) and task.result.get('status') == 'error':
                        if speech_recognition.is_processing():
                            speech_recognition.fail_task(request.user, start_datetime=task.started, end_datetime=task.stopped)
                        return JsonResponse({
                            'status': 'failed',
                            'message': task.result.get('message', '알 수 없는 오류')
                        })
                elif not task.success:
                    logger.error(f"비동기 작업 예외 발생: {task.result}")
                    if isinstance(task.result, dict):
                        error_message = task.result.get('message', '알 수 없는 오류')
                    else:
                        error_message = '😱 시스템 예외가 발생했어요.\n관리자에게 문의해 주세요.'

                    return JsonResponse({
                        'status': 'failed',
                        'message': error_message
                    })

            if speech_recognition.is_processing():
                return JsonResponse({
                    'status': speech_recognition.task_status_code,
                    'task_id': speech_recognition.task_id,
                    'message': f"🛠‍ 전사 작업 {speech_recognition.get_task_status()}을(를) 하고 있어요. 예상 소요 시간: 약 {speech_recognition.get_remaining_estimated_minute() + Summarization.get_estimated_minute()}분"
                })
            if speech_recognition.is_failed():
                return JsonResponse({
                    'status': speech_recognition.task_status_code,
                    'message': f"😱 전사 작업을 실패했어요. 소요 시간: 약 {speech_recognition.get_task_minute()}분",
                })
            if speech_recognition.is_completed():
                summarization = recording.latest_summarization
                if summarization is None:
                    raise Exception('전사 작업은 완료되었으나, 저장된 데이터를 확인할 수 없음')

                if summarization.is_processing():
                    return JsonResponse({
                        'status': summarization.task_status_code,
                        'task_id': summarization.task_id,
                        'message': f"🛠‍ 교정·요약 작업을 하고 있어요. 예상 소요 시간: 약 {summarization.get_remaining_estimated_minute()}분"
                    })

                if summarization.is_failed():
                    return JsonResponse({
                        'status': summarization.task_status_code,
                        'message': f"😱 교정·요약 작업을 실패 했어요. 소요 시간: 약 {summarization.get_task_minute()}분",
                    })

                if summarization.is_completed():
                    return JsonResponse({
                        'status': summarization.task_status_code,
                        'recording_id': recording_id,
                        'speech_recognition_id': speech_recognition.id,
                        'summarization_id': summarization.id,
                        'message': f"👍 전사 및 교정·요약 작업이 완료되었어요. 소요 시간: 약 {speech_recognition.get_task_minute() + summarization.get_task_minute()}분",
                    })
        except Exception as e:
            traceback.print_exc()
            logger.error(f"전사 작업 상태 조회 중 예외 발생: {e}")
            return JsonResponse({'status': 'error', 'message': '😱 전사 작업 상태 확인 중 시스템 예외가 발생했어요.'}, status=500)
