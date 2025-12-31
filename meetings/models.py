import logging
from datetime import timedelta

from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import OuterRef, Subquery, Count, Q
from django.utils import timezone
from django_q.tasks import async_task
from pydub import AudioSegment

from accounts.caches import DepartmentCache
from accounts.models import Department, User
from common.bases import BaseCode
from common.mixins import PrefetchValidationMixin
from common.models import Base, CreatedBase
from config import settings
from reservations.models import Reservation

logger = logging.getLogger(__name__)
GEMINI_3_FLASH_MODEL_NAME = 'gemini-3-flash-preview'
GEMINI_3_FLASH_MODEL_ESTIMATED_MINUTE = 5
GEMINI_2_5_PRO_MODEL_NAME = 'gemini-2.5-pro'
GEMINI_2_5_PRO_MODEL_ESTIMATED_MINUTE = 5
GEMINI_2_5_FLASH_MODEL_NAME = 'gemini-2.5-flash'
GEMINI_2_5_FLASH_MODEL_ESTIMATED_MINUTE = 3


class MeetingTypeCode(BaseCode):
    RESERVATION = 'RESERVATION', '예약 회의'
    STANDALONE = 'STANDALONE', '일반 회의'


class TaskStatusCode(BaseCode):
    WAITING = 'waiting', '대기'
    PROCESSING = 'processing', '처리'
    COMPLETED = 'completed', '완료'
    FAILED = 'failed', '실패'


class SpeechRecognitionStepCode(BaseCode):
    SPEECH_RECOGNITION = 'speech_recognition', '음성 인식(ASR)'  # 음성 파일을 텍스트로 변환(화자 정보 없이, 텍스트와 대략적인 세그먼트 시간만 생성)
    ALIGNMENT = 'alignment', '단어 정렬'  # 정확한 단어별 시간 정보와 매핑
    DIARIZATION = 'diarization', '화자 분리'  # 누가, 언제 말했는지 분석하여 화자 레이블과 시간 범위를 생성
    ASSIGNMENT = 'assignment', '화자 할당'  # 각 단어에 정확한 화자 레이블을 할당
    SAVE_RESULT = 'save', '결과 저장'  # 데이터베이스에 결과 저장
    COMPLETION = 'completion', '완료'


class SummarizationStepCode(BaseCode):
    PREPARATION = 'preparation', '준비'
    REQUEST = 'request', '요청'
    SAVE_RESULT = 'save', '결과 저장'
    COMPLETION = 'completion', '완료'


class Meeting(Base, PrefetchValidationMixin):
    id = models.BigAutoField(primary_key=True)
    type = models.CharField(
        max_length=16,
        choices=MeetingTypeCode.choices,
        default=MeetingTypeCode.STANDALONE,
        verbose_name='회의 유형'
    )
    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name='meeting',
        verbose_name='예약'
    )

    title = models.CharField(max_length=128, verbose_name='제목')
    memo = models.TextField(null=True, blank=True, max_length=1024, verbose_name='메모')
    minutes_content = models.TextField(null=True, blank=True, verbose_name='회의록 내용')
    start_datetime = models.DateTimeField(default=timezone.now, verbose_name='시작 시간')
    end_datetime = models.DateTimeField(null=True, blank=True, verbose_name='종료 시간')
    is_open = models.BooleanField(default=False, verbose_name='공개여부')
    is_active = models.BooleanField(default=True, verbose_name='사용여부')
    attendees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="Attendee",
        through_fields=("meeting", "user"),
        related_name="meetings",
        verbose_name="참석자"
    )

    class Meta:
        db_table = 'meetings_meeting'
        verbose_name = '회의'
        verbose_name_plural = '회의 목록'
        indexes = [
            models.Index(fields=['start_datetime', 'end_datetime'], name='idx_meeting_01'),
        ]

    def __str__(self):
        return f"{self.title}"

    def can_edit(self, user):
        if user.is_superuser:
            return True

        if self.created_user_id == user.id:
            return True

        if self.exists_in_prefetched('attendees', user.pk):
            return True

        created_groups = set(self.created_user.groups.values_list('pk', flat=True))
        user_groups = set(user.groups.values_list('pk', flat=True))

        for created_group in created_groups:
            try:
                ancestors = (DepartmentCache.find_by_group_id(created_group)
                             .get_ancestors(include_self=True if user.is_leader else False))
                for ancestor in ancestors:
                    if ancestor.pk in user_groups:
                        return True
            except Department.DoesNotExist:
                continue

        return False

    def can_view(self, user, edit=None):
        if self.is_open:
            return True

        if edit is not None:
            return edit

        return self.can_edit(user)

    def clean(self):
        super().clean()

        if self.end_datetime and self.end_datetime <= self.start_datetime:
            raise ValidationError({
                'end_datetime': '종료 일시는 시작 일시보다 이후여야 합니다.',
            })

    def save_attendees(self, attendees: set[int], updated_user):
        existing_attendees = set(self.attendees.values_list('pk', flat=True))

        delete_attendees = existing_attendees - attendees
        insert_attendees = attendees - existing_attendees

        if delete_attendees:
            Attendee.objects.filter(meeting=self, user_id__in=delete_attendees).delete()

        new_attendees = [
            Attendee(meeting=self, user_id=user_id, created_user=updated_user)
            for user_id in insert_attendees
        ]
        if new_attendees:
            Attendee.objects.bulk_create(new_attendees, ignore_conflicts=True)

        return {
            "deleted": len(delete_attendees),
            "added": len(insert_attendees)
        }


class Attendee(CreatedBase):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='id')
    meeting = models.ForeignKey(Meeting, on_delete=models.RESTRICT, related_name='meeting_attendee_set', verbose_name='예약')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='meeting_attendee_set', verbose_name='사용자')

    class Meta:
        db_table = "meetings_attendee"
        verbose_name = "참석자"
        verbose_name_plural = "참석자 목록"
        unique_together = ("meeting", "user")

    def __str__(self):
        return f"{self.user} @ {self.meeting}"


def get_recording_upload_path(instance, filename):
    now = timezone.now()
    return f"recordings/{now.year}/{now.month:02d}/{now.day:02d}/{filename}"


class Recording(Base):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='id')
    content_type = models.CharField(max_length=128, blank=True, verbose_name='파일종류')
    upload_file = models.FileField(null=True, blank=True, upload_to=get_recording_upload_path, verbose_name='업로드 파일')
    upload_file_size = models.BigIntegerField(null=True, blank=True, default=0, verbose_name='업로드 파일 크기')
    upload_file_name = models.CharField(null=True, blank=True, max_length=256, verbose_name='업로드 파일 명')
    webm_file = models.FileField(null=True, blank=True, max_length=256, upload_to=get_recording_upload_path, verbose_name='webm 파일')
    webm_file_size = models.BigIntegerField(null=True, blank=True, default=0, verbose_name='webm 파일 크기')
    play_millisecond = models.IntegerField(default=0, verbose_name='재생 밀리초')
    meeting = models.ForeignKey('Meeting', on_delete=models.RESTRICT, verbose_name='회의')
    latest_speech_recognition = models.ForeignKey('SpeechRecognition', null=True, blank=True, on_delete=models.RESTRICT, related_name='+', verbose_name='최근 음성 인식')
    latest_summarization = models.ForeignKey('Summarization', null=True, blank=True, on_delete=models.RESTRICT, related_name='+', verbose_name='최근 요약')
    is_active = models.BooleanField(default=True, verbose_name='사용여부')

    @staticmethod
    def find_by_id_with_latest_tasks(id: int):
        return Recording.objects.select_related('latest_speech_recognition', 'latest_summarization').get(pk=id)

    @staticmethod
    def find_by_speech_recognition_id_with_latest_tasks(speech_recognition_id: int):
        return Recording.objects.select_related('latest_speech_recognition', 'latest_summarization').get(latest_speech_recognition__id=speech_recognition_id)

    def can_speech_recognition_task(self):
        return self.latest_speech_recognition is None or self.latest_speech_recognition.is_failed()

    def start_speech_recognition_task(self, user: User):
        if not self.can_speech_recognition_task():
            raise ValidationError('전사 작업을 시작할 수 없어요.')

        task_id = async_task('meetings.tasks.run_speech_recognition', self.id, user.id)

        speech_recognition = SpeechRecognition.objects.create(
            task_id=task_id,
            task_status_code=TaskStatusCode.WAITING,
            recording=self,
            created_user=user,
            last_modified_user=user,
        )

        self.set_latest_speech_recognition(speech_recognition, user)

    def set_latest_speech_recognition(self, speech_recognition, user):
        self.latest_speech_recognition = speech_recognition
        self.last_modified_user = user
        self.last_modified_date = timezone.now()

        self.save(update_fields=['latest_speech_recognition', 'last_modified_user', 'last_modified_date'])

    def set_latest_summarization(self, summarization, user):
        self.latest_summarization = summarization
        self.last_modified_user = user
        self.last_modified_date = timezone.now()

        self.save(update_fields=['latest_summarization', 'last_modified_user', 'last_modified_date'])

    def is_processing_speech_recognition(self):
        return self.latest_speech_recognition and self.latest_speech_recognition.is_processing()

    def is_completed_speech_recognition(self):
        return self.latest_speech_recognition and self.latest_speech_recognition.is_completed()

    def is_failed_speech_recognition(self):
        return self.latest_speech_recognition and self.latest_speech_recognition.is_failed()

    def save(self, *args, **kwargs):
        is_new = not self.pk

        super().save(*args, **kwargs)

        if is_new:
            if self.webm_file:
                try:
                    audio = AudioSegment.from_file(self.webm_file.path)
                    self.play_millisecond = len(audio)
                    super().save(update_fields=['play_millisecond'])
                except Exception as e:
                    logger.error(f"Audio duration read failed: {e}")
                    self.play_millisecond = 0
            else:
                self.play_millisecond = 0

    class Meta:
        db_table = 'meetings_recording'
        verbose_name = '녹음'
        verbose_name_plural = '녹음 목록'

    def __str__(self):
        return f"Recording #{self.pk}"


class SpeechRecognition(Base):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='id')
    task_id = models.CharField(max_length=32, verbose_name='작업 id')
    speech_recognition_model_name = models.CharField(max_length=64, verbose_name='음성 인식 모델 이름')
    align_model_name = models.CharField(max_length=64, verbose_name='정렬 모델 이름')
    diarization_model_name = models.CharField(max_length=64, verbose_name='화자 분리 모델 이름')
    task_start_datetime = models.DateTimeField(null=True, blank=True, verbose_name='작업 시작 시간')
    speech_recognition_end_datetime = models.DateTimeField(null=True, blank=True, verbose_name='음성 인식 종료 시간')
    align_end_datetime = models.DateTimeField(null=True, blank=True, verbose_name='정렬 종료 시간')
    diarization_end_datetime = models.DateTimeField(null=True, blank=True, verbose_name='화자 분리 종료 시간')
    assignment_end_datetime = models.DateTimeField(null=True, blank=True, verbose_name='할당 종료 시간')
    task_end_datetime = models.DateTimeField(null=True, blank=True, verbose_name='작업 종료 시간')
    task_step_code = models.CharField(max_length=32, null=True, blank=True, verbose_name='작업 단계 코드')
    task_status_code = models.CharField(max_length=16, verbose_name='작업 상태 코드')
    language_code = models.CharField(max_length=2, null=True, blank=True, verbose_name='언어 코드')
    recording = models.ForeignKey('Recording', on_delete=models.RESTRICT, related_name='speech_recognition_set', verbose_name='녹음')

    @staticmethod
    def find_by_id_with_latest_summarization(id: int):
        if id is None:
            raise ValidationError('음성 인식 식별자를 확인해 주세요.')

        latest_summarization_id_subquery = Summarization.objects.filter(
            speech_recognition_id=OuterRef('pk')
        ).order_by('-pk').values('pk')[:1]

        speech_recognitions_with_latest_id_qs = SpeechRecognition.objects.annotate(
            latest_summarization_id=Subquery(latest_summarization_id_subquery)
        )

        speech_recognition = speech_recognitions_with_latest_id_qs.get(pk=id)

        latest_summarization_id = speech_recognition.latest_summarization_id
        latest_summarization = None

        if latest_summarization_id is not None:
            latest_summarization = Summarization.objects.filter(pk=latest_summarization_id).first()

        speech_recognition.latest_summarization = latest_summarization

        return speech_recognition

    def get_latest_summarization(self):
        if not getattr(self, 'latest_summarization', None):
            latest_summarization = Summarization.objects.filter(
                speech_recognition_id=self.pk
            ).order_by('-pk').all().first()
            self.latest_summarization = latest_summarization

        return self.latest_summarization

    def get_estimated_minute(self) -> int | None:
        if self.recording.play_millisecond > 0:
            duration_sec = self.recording.play_millisecond / 1000
            estimated_time_per_60_sec = 60
            estimated_time_second = int(duration_sec / 60 * estimated_time_per_60_sec)
            estimated_time_minute = max(1, estimated_time_second // 60)
            return estimated_time_minute
        return 1

    def get_remaining_estimated_minute(self) -> int | None:
        estimated_minute = self.get_estimated_minute()
        if estimated_minute is None:
            return 1

        start_time = self.task_start_datetime
        if not start_time:
            return estimated_minute

        now = timezone.now()
        time_elapsed = now - start_time

        estimated_duration = timedelta(minutes=estimated_minute)

        time_remaining = estimated_duration - time_elapsed

        if time_remaining.total_seconds() > 0:
            import math
            remaining_seconds = time_remaining.total_seconds()
            return math.ceil(remaining_seconds / 60)
        else:
            return 1

    def get_task_minute(self) -> int | None:
        start_datetime = self.task_start_datetime
        if not start_datetime:
            return None

        end_datetime = self.task_end_datetime
        if end_datetime is None:
            return None

        duration = end_datetime - start_datetime

        if duration.total_seconds() > 0:
            import math
            remaining_seconds = duration.total_seconds()
            return math.ceil(remaining_seconds / 60)
        else:
            return 0

    def get_task_status(self):
        if self.task_status_code is None:
            return None
        if self.task_status_code == TaskStatusCode.PROCESSING:
            return SpeechRecognitionStepCode.find_by_value(self.task_step_code).label
        return TaskStatusCode.find_by_value(self.task_status_code).label

    def is_processing(self):
        return self.task_status_code == TaskStatusCode.WAITING or self.task_status_code == TaskStatusCode.PROCESSING

    def is_completed(self):
        return self.task_status_code == TaskStatusCode.COMPLETED

    def is_failed(self):
        return self.task_status_code == TaskStatusCode.FAILED

    def transcribe(self, user):
        self.task_start_datetime = timezone.now()
        self.task_step_code = SpeechRecognitionStepCode.SPEECH_RECOGNITION
        self.task_status_code = TaskStatusCode.PROCESSING
        self.last_modified_user = user
        self.last_modified_date = timezone.now()

        self.save(update_fields=['task_start_datetime', 'task_step_code', 'task_status_code', 'last_modified_user', 'last_modified_date'])

    def align(self, language_code, user):
        self.task_step_code = SpeechRecognitionStepCode.ALIGNMENT
        self.speech_recognition_end_datetime = timezone.now()
        self.language_code = language_code
        self.last_modified_user = user
        self.last_modified_date = timezone.now()

        self.save(update_fields=['task_step_code', 'speech_recognition_end_datetime', 'language_code', 'last_modified_user', 'last_modified_date'])

    def diarize(self, user):
        self.task_step_code = SpeechRecognitionStepCode.DIARIZATION
        self.align_end_datetime = timezone.now()
        self.last_modified_user = user
        self.last_modified_date = timezone.now()

        self.save(update_fields=['task_step_code', 'align_end_datetime', 'last_modified_user', 'last_modified_date'])

    def assign(self, user):
        self.task_step_code = SpeechRecognitionStepCode.ASSIGNMENT
        self.diarization_end_datetime = timezone.now()
        self.last_modified_user = user
        self.last_modified_date = timezone.now()

        self.save(update_fields=['task_step_code', 'diarization_end_datetime', 'last_modified_user', 'last_modified_date'])

    def save_result(self, result, user):
        self.speech_recognition_model_name = result.get('speech_recognition_model_name')
        self.align_model_name = result.get('align_model_name')
        self.diarization_model_name = result.get('diarization_model_name')
        self.task_step_code = SpeechRecognitionStepCode.SAVE_RESULT
        self.assignment_end_datetime = timezone.now()
        self.last_modified_user = user
        self.last_modified_date = timezone.now()

        self.save(update_fields=['speech_recognition_model_name', 'align_model_name', 'diarization_model_name', 'task_step_code', 'assignment_end_datetime', 'last_modified_user',
                                 'last_modified_date'])

    def complete_task(self, user: User):
        if not self.is_processing():
            raise ValidationError('완료 처리가 불가한 상태에요.')

        self.task_end_datetime = timezone.now()
        self.task_step_code = SpeechRecognitionStepCode.COMPLETION
        self.task_status_code = TaskStatusCode.COMPLETED
        self.last_modified_user = user
        self.last_modified_date = timezone.now()

        self.save(update_fields=['task_end_datetime', 'task_step_code', 'task_status_code', 'last_modified_user', 'last_modified_date'])

        self.start_summarization_task(user)

    def fail_task(self, user: User, start_datetime=None, end_datetime=timezone.now()):
        if not self.is_processing():
            raise ValidationError('실패 처리가 불가한 상태에요.')

        update_fields = ['task_end_datetime', 'task_status_code', 'last_modified_user', 'last_modified_date']

        if self.task_start_datetime is None:
            self.task_start_datetime = start_datetime
            update_fields.append('start_datetime')

        self.task_end_datetime = end_datetime
        self.task_status_code = TaskStatusCode.FAILED
        self.last_modified_user = user
        self.last_modified_date = timezone.now()

        self.save(update_fields=update_fields)

    def can_summarization_task(self):
        return self.recording.latest_summarization is None or self.recording.latest_summarization.is_failed()

    def start_summarization_task(self, user: User):
        if not self.can_summarization_task():
            raise ValidationError('전사 작업을 시작할 수 없어요.')

        task_id = async_task('meetings.tasks.run_correction_and_summarization', self.id, user.id)

        summarization = Summarization.objects.create(
            task_id=task_id,
            task_status_code=TaskStatusCode.WAITING,
            speech_recognition=self,
            created_user=user,
            last_modified_user=user,
        )

        self.recording.set_latest_summarization(summarization, user)

        return summarization

    @classmethod
    def get_count(cls):
        return SpeechRecognition.objects.aggregate(
            speech_recognition_count=Count(
                'id',
                filter=Q(task_step_code=SpeechRecognitionStepCode.SPEECH_RECOGNITION)
            ),
            alignment_count=Count(
                'id',
                filter=Q(task_step_code=SpeechRecognitionStepCode.ALIGNMENT)
            ),
            diarization_count=Count(
                'id',
                filter=Q(task_step_code=SpeechRecognitionStepCode.DIARIZATION)
            ),
            assignment_count=Count(
                'id',
                filter=Q(task_step_code=SpeechRecognitionStepCode.ASSIGNMENT)
            ),
            waiting_count=Count(
                'id',
                filter=Q(task_status_code=TaskStatusCode.WAITING)
            ),
            processing_count=Count(
                'id',
                filter=Q(task_status_code=TaskStatusCode.PROCESSING)
            ),
            completed_count=Count(
                'id',
                filter=Q(task_status_code=TaskStatusCode.COMPLETED)
            ),
            failed_count=Count(
                'id',
                filter=Q(task_status_code=TaskStatusCode.FAILED)
            ),
        )

    class Meta:
        db_table = 'meetings_speech_recognition'
        verbose_name = '음성 인식'
        verbose_name_plural = '음성 인식 목록'
        indexes = [
            models.Index(
                fields=['task_status_code'],
                name='idx_speech_recognition_01'
            ),
            models.Index(
                fields=['task_step_code'],
                name='idx_speech_recognition_02'
            ),
        ]

    def __str__(self):
        return f"SpeechRecognition #{self.pk}"


class Speaker(Base):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='id')
    speaker_label = models.CharField(max_length=64, verbose_name='화자 레이블')
    meeting = models.ForeignKey('Meeting', on_delete=models.CASCADE, verbose_name='회의')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, null=True, blank=True, verbose_name='매핑된 사용자')
    original_recording = models.ForeignKey('Recording', on_delete=models.RESTRICT, null=True, blank=True, verbose_name='원본 녹음')

    class Meta:
        db_table = 'meetings_speaker'
        verbose_name = '화자'
        verbose_name_plural = '화자 목록'

    def __str__(self):
        return self.speaker_label


class Segment(Base):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='id')
    text = models.TextField(verbose_name='문자')
    start_millisecond = models.IntegerField(null=True, blank=True, verbose_name='시작 밀리초')
    end_millisecond = models.IntegerField(null=True, blank=True, verbose_name='종료 밀리초')
    corrected_text = models.TextField(null=True, blank=True, verbose_name='교정된 문자')
    speech_recognition = models.ForeignKey('SpeechRecognition', on_delete=models.CASCADE, verbose_name='음성 인식')
    speaker = models.ForeignKey('Speaker', on_delete=models.CASCADE, verbose_name='화자')

    class Meta:
        db_table = 'meetings_segment'
        verbose_name = '부분'
        verbose_name_plural = '부분 목록'

    def __str__(self):
        return f"{self.start_millisecond} ~ {self.end_millisecond} {self.text}"


class Word(Base):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='id')
    word = models.CharField(max_length=128, verbose_name='단어')
    score = models.FloatField(verbose_name='점수')
    start_millisecond = models.IntegerField(null=True, blank=True, verbose_name='시작 밀리초')
    end_millisecond = models.IntegerField(null=True, blank=True, verbose_name='종료 밀리초')
    corrected_word = models.CharField(max_length=128, null=True, blank=True, verbose_name='교정된 단어')
    is_correction_removed = models.BooleanField(default=False, verbose_name='교정 삭제 여부')
    segment = models.ForeignKey('Segment', on_delete=models.CASCADE, verbose_name='부분')
    speaker = models.ForeignKey('Speaker', on_delete=models.CASCADE, verbose_name='화자')

    class Meta:
        db_table = 'meetings_word'
        verbose_name = '단어'
        verbose_name_plural = '단어 목록'
        indexes = [
            GinIndex(
                fields=['word'],
                name='idx_trgm_word_01',
                opclasses=['gin_trgm_ops'] # 중요: Trigram 연산을 위한 옵션
            ),
            GinIndex(
                fields=['corrected_word'],
                name='idx_trgm_word_02',
                opclasses=['gin_trgm_ops']
            ),
        ]

    def __str__(self):
        return self.word


class Summarization(Base):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='id')
    task_id = models.CharField(max_length=32, verbose_name='작업 id')
    generative_ai_model_name = models.CharField(max_length=64, null=True, blank=True, verbose_name='생성형 AI 모델 이름')
    task_start_datetime = models.DateTimeField(null=True, blank=True, verbose_name='작업 시작 시간')
    task_end_datetime = models.DateTimeField(null=True, blank=True, verbose_name='작업 종료 시간')
    task_step_code = models.CharField(max_length=32, null=True, blank=True, verbose_name='작업 단계 코드')
    task_status_code = models.CharField(max_length=16, verbose_name='작업 상태 코드')
    summarization_content = models.TextField(null=True, blank=True, verbose_name='요약 내용')
    minutes_content = models.TextField(null=True, blank=True, verbose_name='회의록 내용')
    action_items = models.JSONField(null=True, blank=True, verbose_name='액션 아이템')
    speech_recognition = models.ForeignKey('SpeechRecognition', on_delete=models.RESTRICT, related_name='summarization_set', verbose_name='음성 인식')

    @staticmethod
    def find_by_latest_speech_recognition_id(speech_recognition_id: int):
        if speech_recognition_id is None:
            raise ValidationError('음성 인식 식별자를 확인해 주세요.')

        return Summarization.objects.filter(
            speech_recognition_id=speech_recognition_id
        ).order_by('-pk').all().first()

    @staticmethod
    def get_estimated_minute() -> int | None:
        return GEMINI_3_FLASH_MODEL_ESTIMATED_MINUTE

    def get_remaining_estimated_minute(self) -> int | None:
        estimated_minute = Summarization.get_estimated_minute()

        start_datetime = self.task_start_datetime
        if not start_datetime:
            return estimated_minute

        now = timezone.now()
        time_elapsed = now - start_datetime

        estimated_duration = timedelta(minutes=estimated_minute)

        time_remaining = estimated_duration - time_elapsed

        if time_remaining.total_seconds() > 0:
            import math
            remaining_seconds = time_remaining.total_seconds()
            return math.ceil(remaining_seconds / 60)
        else:
            return 1

    def get_task_minute(self) -> int | None:
        start_datetime = self.task_start_datetime
        if not start_datetime:
            return None

        end_datetime = self.task_end_datetime
        if end_datetime is None:
            return None

        duration = end_datetime - start_datetime

        if duration.total_seconds() > 0:
            import math
            remaining_seconds = duration.total_seconds()
            return math.ceil(remaining_seconds / 60)
        else:
            return 0

    def can_task(self):
        return self.task_status_code == TaskStatusCode.FAILED

    def is_processing(self):
        return self.task_status_code == TaskStatusCode.WAITING or self.task_status_code == TaskStatusCode.PROCESSING

    def is_completed(self):
        return self.task_status_code == TaskStatusCode.COMPLETED

    def is_failed(self):
        return self.task_status_code == TaskStatusCode.FAILED

    def prepare(self, user: User):
        self.task_step_code = SummarizationStepCode.PREPARATION
        self.task_start_datetime = timezone.now()
        self.task_status_code = TaskStatusCode.PROCESSING
        self.last_modified_user = user
        self.last_modified_date = timezone.now()

        self.save(update_fields=['task_start_datetime', 'task_step_code', 'task_status_code', 'last_modified_user', 'last_modified_date'])

    def request(self, user: User):
        self.task_step_code = SummarizationStepCode.REQUEST
        self.last_modified_user = user
        self.last_modified_date = timezone.now()

        self.save(update_fields=['task_step_code', 'last_modified_user', 'last_modified_date'])

    def save_result(self, generative_ai_model_name, user: User):
        self.generative_ai_model_name = generative_ai_model_name
        self.task_step_code = SummarizationStepCode.SAVE_RESULT
        self.last_modified_user = user
        self.last_modified_date = timezone.now()

        self.save(update_fields=['generative_ai_model_name', 'task_step_code', 'last_modified_user', 'last_modified_date'])

    def fail_task(self, generative_ai_model_name, user: User):
        if not self.is_processing():
            raise ValidationError('실패 처리가 불가한 상태에요.')

        self.generative_ai_model_name = generative_ai_model_name
        self.task_end_datetime = timezone.now()
        self.task_status_code = TaskStatusCode.FAILED
        self.last_modified_user = user
        self.last_modified_date = timezone.now()

        self.save(update_fields=['generative_ai_model_name', 'task_end_datetime', 'task_status_code', 'last_modified_user', 'last_modified_date'])

    def complete_task(self, gemini_result, user: User):
        if not self.is_processing():
            raise ValidationError('완료 처리가 불가한 상태에요.')

        self.task_end_datetime = timezone.now()
        self.task_step_code = SummarizationStepCode.COMPLETION
        self.task_status_code = TaskStatusCode.COMPLETED
        self.summarization_content = gemini_result.get('general_summarization', None)
        self.minutes_content = gemini_result.get('meeting_minutes', None)
        self.action_items = gemini_result.get('action_items', None)
        self.last_modified_user = user
        self.last_modified_date = timezone.now()

        self.save(update_fields=['task_end_datetime', 'task_step_code', 'task_status_code', 'summarization_content', 'minutes_content', 'action_items',
                                 'last_modified_user', 'last_modified_date'])

    @classmethod
    def get_count(cls):
        return Summarization.objects.aggregate(
            waiting_count=Count(
                'id',
                filter=Q(task_status_code=TaskStatusCode.WAITING)
            ),
            processing_count=Count(
                'id',
                filter=Q(task_status_code=TaskStatusCode.PROCESSING)
            ),
            completed_count=Count(
                'id',
                filter=Q(task_status_code=TaskStatusCode.COMPLETED)
            ),
            failed_count=Count(
                'id',
                filter=Q(task_status_code=TaskStatusCode.FAILED)
            ),
        )

    class Meta:
        db_table = 'meetings_summarization'
        verbose_name = '요약'
        verbose_name_plural = '요약 목록'
        indexes = [
            models.Index(
                fields=['task_status_code'],
                name='idx_summarization_01'
            ),
        ]

    def __str__(self):
        return f"Summarization #{self.pk}"
