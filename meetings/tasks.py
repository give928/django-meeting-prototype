import difflib
import json
import logging
import time
import traceback
from collections import defaultdict
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from google import genai
from google.genai import types
from google.genai.errors import APIError

from meetings.models import Recording, SpeechRecognition, Speaker, Segment, Word, Summarization, GEMINI_2_5_PRO_MODEL_NAME, GEMINI_2_5_FLASH_MODEL_NAME, GEMINI_3_FLASH_MODEL_NAME
from .errors import GeminiApiError
from .utils import RecordingUtils

logger = logging.getLogger(__name__)
User = get_user_model()
UNKNOWN_SPEAKER_LABEL = 'UNKNOWN'
_MAX_RETRIES = 5


def run_speech_recognition(recording_id: int, user_id: int):
    logger.info(f"전사 작업 시작: Recording #{recording_id}")

    try:
        recording = Recording.find_by_id_with_latest_tasks(recording_id)
    except SpeechRecognition.DoesNotExist as e:
        logger.error(f"전사 작업 실패 (Recording #{recording_id}): {e}")
        return {'status': 'error', 'message': '녹음 파일 정보를 확인할 수 없어요.'}
    except SpeechRecognition.DoesNotExist as e:
        logger.error(f"전사 작업 실패 (Recording #{recording_id}): {e}")
        return {'status': 'error', 'message': '음성 인식 작업 정보를 확인할 수 없어요.'}
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist as e:
        logger.error(f"전사 작업 실패 (Recording #{recording_id}): {e}")
        return {'status': 'error', 'message': '사용자 정보를 확인할 수 없어요.'}

    try:
        if recording.latest_speech_recognition.is_completed():
            if recording.latest_speech_recognition.can_summarization_task():
                recording.latest_speech_recognition.start_summarization_task(user)
            summarization = recording.latest_summarization
            return {'status': summarization.task_status_code, 'summarization_id': summarization.pk}

        speech_recognition = recording.latest_speech_recognition

        with transaction.atomic():
            speech_recognition.transcribe(user)

        file_path = recording.webm_file.path

        transcription_result = RecordingUtils.transcribe(file_path)

        language_code = transcription_result.get("language", 'ko')

        with transaction.atomic():
            speech_recognition.align(language_code, user)

        aligned = RecordingUtils.align(file_path, language_code, transcription_result['segments'])

        with transaction.atomic():
            speech_recognition.diarize(user)

        diarized = RecordingUtils.diarize(file_path)

        with transaction.atomic():
            speech_recognition.assign(user)

        result = RecordingUtils.assign(aligned, diarized)

        with transaction.atomic():
            speech_recognition.save_result(result, user)

        segments_data = result.get('segments', [])

        speaker_labels = set()
        for s in segments_data:
            if 'speaker' not in s:
                s['speaker'] = UNKNOWN_SPEAKER_LABEL

            speaker_labels.add(s['speaker'])

        with transaction.atomic():
            speaker_map = {}
            for label in speaker_labels:
                speaker, _ = Speaker.objects.get_or_create(
                    speaker_label=label,
                    meeting=recording.meeting,
                    defaults={
                        'original_recording': recording,
                        'created_user': user,
                        'last_modified_user': user
                    }
                )
                speaker_map[label] = speaker

            words_to_create = []

            merged_segments = []
            if segments_data:
                current_segment = segments_data[0]
                current_segment['words'] = current_segment.get('words', [])

                for next_segment in segments_data[1:]:
                    if next_segment['speaker'] == current_segment['speaker']:
                        current_text_strip = current_segment['text'].strip()
                        if current_text_strip and current_text_strip[-1] in ['.', '?', '!', '요']:  # 한국어 구어체 특성상 문장 종결을 나타내는 문자
                            separator = "\n"
                        else:
                            separator = " "

                        current_segment['end'] = next_segment['end']
                        current_segment['text'] += separator + next_segment['text']
                        current_segment['words'].extend(next_segment.get('words', []))
                    else:
                        merged_segments.append(current_segment)
                        current_segment = next_segment
                        current_segment['words'] = current_segment.get('words', [])
                merged_segments.append(current_segment)

            for segment_data in merged_segments:
                speaker_label = segment_data['speaker']
                speaker = speaker_map[speaker_label]

                start_ms = int(segment_data['start'] * 1000)
                end_ms = int(segment_data['end'] * 1000)

                segment = Segment.objects.create(
                    start_millisecond=start_ms,
                    end_millisecond=end_ms,
                    text=segment_data['text'].strip(),
                    speech_recognition=speech_recognition,
                    speaker=speaker,
                    created_user=user,
                    last_modified_user=user,
                )

                for word_data in segment_data['words']:
                    word_start_ms = int(word_data['start'] * 1000)
                    word_end_ms = int(word_data['end'] * 1000)

                    words_to_create.append(
                        Word(
                            word=word_data['word'],
                            score=word_data.get('score', 0.0),
                            start_millisecond=word_start_ms,
                            end_millisecond=word_end_ms,
                            search_content=word_data['word'],
                            segment=segment,
                            speaker=speaker,
                            created_user=user,
                            last_modified_user=user,
                        )
                    )

            if words_to_create:
                Word.objects.bulk_create(words_to_create)

            speech_recognition.complete_task(user)

        logger.info(f"전사 작업 완료: Recording #{recording_id} SpeechRecognition #{speech_recognition.id}")

        return {'status': speech_recognition.task_status_code, 'recording_id': recording_id, 'speech_recognition_id': speech_recognition.id}
    except Exception as e:
        traceback.print_exc()
        logger.error(f"전사 작업 실패 (Recording #{recording_id} SpeechRecognition #{recording.latest_speech_recognition.id}): {e}")
        with transaction.atomic():
            recording.latest_speech_recognition.fail_task(user)
        return {'status': 'error', 'message': f"전사 작업 중 예외가 발생했어요. {e}"}


def run_correction_and_summarization(speech_recognition_id: int, user_id: int) -> dict:
    logger.info(f"교정·요약 작업 시작: SpeechRecognition #{speech_recognition_id}")

    try:
        recording = Recording.find_by_speech_recognition_id_with_latest_tasks(speech_recognition_id)
        summarization = recording.latest_summarization
        if summarization is None:
            raise Summarization.DoesNotExist()
    except Recording.DoesNotExist as e:
        logger.error(f"교정·요약 작업 실패 (SpeechRecognition #{speech_recognition_id}): {e}")
        return {'status': 'error', 'message': '전사 정보를 확인할 수 없어요.'}
    except Summarization.DoesNotExist as e:
        logger.error(f"교정·요약 작업 실패 (SpeechRecognition #{speech_recognition_id}): {e}")
        return {'status': 'error', 'message': '전사 정보를 확인할 수 없어요.'}
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist as e:
        logger.error(f"교정·요약 작업 실패 (SpeechRecognition #{speech_recognition_id} User #{user_id}): {e}")
        return {'status': 'error', 'message': '사용자 정보를 확인할 수 없어요.'}

    try:
        if not summarization.is_processing():
            return {'status': summarization.task_status_code, 'summarization_id': summarization.pk}

        with transaction.atomic():
            summarization.prepare(user)

        full_text_json, original_segments_map = prepare_prompt_data(speech_recognition_id)

        if not full_text_json:
            raise Exception('교정·요약할 내용이 없어요.')

        with transaction.atomic():
            summarization.request(user)

        generative_ai_model_name, gemini_result = call_gemini_for_correction_and_summarization(full_text_json)

        with transaction.atomic():
            summarization.save_result(generative_ai_model_name, user)

        segments = []
        with transaction.atomic():
            segments_to_update = []
            corrected_segments_data = gemini_result.get('corrected_segments', [])

            for item in corrected_segments_data:
                seg_id = item.get('original_segment_id')
                corrected_text = item.get('corrected_text')

                if seg_id in original_segments_map and corrected_text is not None:
                    segment = original_segments_map[seg_id]
                    segment.corrected_text = corrected_text
                    segment.last_modified_user = user
                    segment.last_modified_date = timezone.now()
                    segments_to_update.append(segment)

                segments.append({
                    'id': segment.id,
                    'speaker': segment.speaker.user if segment.speaker.user is not None else segment.speaker.speaker_label,
                    'start': segment.start_millisecond,
                    'end': segment.end_millisecond,
                    'text': segment.text,
                    'corrected_text': segment.corrected_text,
                })

            if segments_to_update:
                Segment.objects.bulk_update(
                    segments_to_update,
                    ['corrected_text', 'last_modified_user', 'last_modified_date']
                )

                correct_words(segments_to_update, user)

            summarization.complete_task(gemini_result, user)

            logger.info(f"교정·요약 완료: SpeechRecognition #{speech_recognition_id} Summarization #{summarization.pk}")

        return {
            'status': summarization.task_status_code,
            'speech_recognition_id': speech_recognition_id,
            'summarization_id': summarization.pk,
        }
    except GeminiApiError as e:
        logger.error(f"교정·요약 작업 실패 (SpeechRecognition #{speech_recognition_id} Summarization #{summarization.pk}): {e}")
        with transaction.atomic():
            summarization.fail_task(e.generative_ai_model_name, user)
        return {'status': 'error', 'message': e.message}
    except Exception as e:
        logger.error(f"교정·요약 작업 실패 (SpeechRecognition #{speech_recognition_id} Summarization #{summarization.pk}): {e}")
        with transaction.atomic():
            summarization.fail_task(None, user)
        return {'status': 'error', 'message': f"교정·요약 작업 중 시스템 예외가 발생했어요. {e}"}


def prepare_prompt_data(speech_recognition_id: int):
    segments = Segment.objects.filter(speech_recognition_id=speech_recognition_id).select_related('speaker').order_by('id')

    if not segments:
        return None, None

    prompt_segments = []
    original_segments_map = {}

    for seg in segments:
        prompt_segments.append({
            "original_segment_id": seg.id,
            "speaker_label": seg.speaker.speaker_label,
            "text": seg.text
        })
        original_segments_map[seg.id] = seg

    # 한국어 처리를 위해 ensure_ascii=False
    full_text_json = json.dumps(prompt_segments, ensure_ascii=False, indent=2)

    return full_text_json, original_segments_map


def call_gemini_for_correction_and_summarization(prompt_data: str) -> tuple[str, Any]:
    # 출력 JSON 스키마 정의
    response_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "general_summarization": types.Schema(
                type=types.Type.STRING,
                description="교정된 전체 내용을 약 10줄로 개괄적으로 요약한 내용입니다."
            ),
            "meeting_minutes": types.Schema(
                type=types.Type.STRING,
                description="회의의 핵심 의제, 주요 논의 결과 및 결정 사항을 문어체, 두괄식으로 압축하여 작성한 공식 회의록 본문입니다."
            ),
            "action_items": types.Schema(
                type=types.Type.ARRAY,
                description="회의 내용에서 도출된 조치 사항(Action Item)을 추출합니다. 각 항목은 '주체: 내용' 또는 '주체(마감일): 내용' 형태로 작성합니다.",
                items=types.Schema(
                    type=types.Type.STRING,
                    description="하나의 구체적인 액션 아이템 (예: 홍길동: 12/31까지 보고서 초안 작성)"
                )
            ),
            "corrected_segments": types.Schema(
                type=types.Type.ARRAY,
                description="각 세그먼트의 교정 결과 리스트입니다.",
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "original_segment_id": types.Schema(
                            type=types.Type.INTEGER,
                            description="요청 시 제공된 Segment의 ID (이 값을 반드시 그대로 반환해야 합니다)."
                        ),
                        "corrected_text": types.Schema(
                            type=types.Type.STRING,
                            description="원본 텍스트를 문법, 오타 등을 교정한 최종 결과 텍스트입니다. 화자 레이블은 포함하지 않습니다."
                        )
                    },
                    required=["original_segment_id", "corrected_text"]
                )
            )
        },
        required=["general_summarization", "meeting_minutes", "action_items", "corrected_segments"]
    )

    # AI의 행동 강령/정체성 부여
    system_instruction = (
        "당신은 회의록 전사 기록을 교정하고 내용을 구조화하여 공식 회의록을 작성하는 전문가입니다. "
        "제공된 데이터를 분석하여 반드시 **지정된 JSON 스키마 형식**으로만 응답해야 합니다.\n\n"
        "**[핵심 원칙]**\n"
        "1. **정확성:** 원본의 의미를 왜곡하지 않고 정확하게 교정해야 합니다.\n"
        "2. **데이터 무결성:** 결과의 'corrected_segments' 리스트에 있는 'original_segment_id'는 입력된 원본 ID와 반드시 일치해야 합니다.\n"
        "3. **가독성 (문단 분리):** 텍스트 교정 시, 다음 기준에 따라 적극적으로 문단을 분리하고 개행 문자('\\n')를 사용하십시오.\n"
        "   - 화자가 바뀌거나 주제가 전환될 때.\n"
        "   - 하나의 문단에는 하나의 중심 생각만 담을 것."
    )

    correct_word_prompt = " 단어의 원형은 가급적 유지하며 문법만 교정하십시오."
    is_correct_word = False  # 단어 교정을 우선으로 하려면

    # 프롬프트
    prompt = f"""
    다음 [데이터]를 바탕으로 아래 4가지 작업을 수행하고 JSON 결과를 반환하십시오.

    **[작업 지시사항]**

    **1. 세그먼트 교정 (corrected_segments)**
    - 각 세그먼트의 'text'를 문법과 오타를 수정하고 자연스러운 문어체로 다듬어 'corrected_text'에 작성하십시오.{correct_word_prompt if is_correct_word else ''}
    - 시스템 지침의 '가독성 원칙'을 적용하여 문단을 적절히 분리하십시오.

    **2. 일반 요약 (general_summarization)**
    - 전체 회의 내용을 약 10줄 내외로 개괄적으로 요약하십시오.
    - 시스템 지침의 '가독성 원칙'을 적용하여 문단을 적절히 분리하십시오.
    
    **3. 회의록 본문 작성 (meeting_minutes)**
    - 전체 내용을 **공식 회의록 스타일(문어체, 두괄식)**로 재구성하십시오.
    - **주요 의제(회의 목적)**, **핵심 논의 내용**, **최종 결정 사항**을 명확한 소제목으로 구분하여 작성하십시오.

    **4. 액션 아이템 추출 (action_items)**
    - 회의 내용 중 실행이 필요한 과업을 찾아 **'담당자: 할 일 (마감기한)'** 형태로 명확히 추출하십시오.

    **[데이터]**
    {prompt_data}
    """

    generative_ai_model_name = GEMINI_3_FLASH_MODEL_NAME

    try:
        client = genai.Client()

        for attempt in range(_MAX_RETRIES):
            try:
                response = client.models.generate_content(
                    model=generative_ai_model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=response_schema,
                        system_instruction=system_instruction
                    ),
                )

                return generative_ai_model_name, json.loads(response.text)
            except APIError as e:
                logger.error(f"Gemini API 호출 실패 (모델: {generative_ai_model_name}, 시도 {attempt + 1}/{_MAX_RETRIES}): {e}")
                error_message = str(e)
                if '429 RESOURCE_EXHAUSTED' in error_message and attempt < _MAX_RETRIES - 1:
                    generative_ai_model_name = GEMINI_2_5_FLASH_MODEL_NAME
                    wait_time = min(60 * (2 ** attempt), 300)  # 60초, 120초, 300초, ... 증가
                    logger.warning(f"Gemini API 429 Quota 초과 발생으로 {wait_time}초 후 재시도합니다. (시도 {attempt + 1}/{_MAX_RETRIES})")
                    time.sleep(wait_time)
                    continue

                raise GeminiApiError(message=error_message, generative_ai_model_name=generative_ai_model_name, exception=e)
            except Exception as e:
                logger.error(f"Gemini API 호출 실패: {e}")
                error_message = str(e)
                if '[Errno 8] nodename nor servname provided, or not known' in error_message:
                    raise GeminiApiError(message=f"서버 네트워크 예외가 발생했어요. 관리자에게 문의해 주세요.", generative_ai_model_name=generative_ai_model_name, exception=e)

                raise GeminiApiError(message=f"시스템 예외({str(e)})", generative_ai_model_name=generative_ai_model_name, exception=e)

        raise GeminiApiError(message='최대 재시도 횟수를 초과하여 Gemini API 호출에 실패했어요.', generative_ai_model_name=generative_ai_model_name)
    except Exception as e:
        logger.error(f"Gemini API 호출 실패: {e}")
        raise GeminiApiError(message=f"시스템 예외({str(e)})", generative_ai_model_name=generative_ai_model_name, exception=e)


def correct_words(segments_to_update, user):
    if not segments_to_update:
        return

    segment_ids = [s.id for s in segments_to_update]
    words = Word.objects.filter(segment_id__in=segment_ids).order_by('segment_id', 'id')

    words_by_segment = defaultdict(list)
    for word in words:
        words_by_segment[word.segment_id].append(word)

    words_to_bulk_update = []
    now = timezone.now()

    for segment in segments_to_update:
        segment_words = words_by_segment.get(segment.id, [])
        if not segment_words:
            continue

        word_texts = [w.word for w in segment_words]
        corrected_word_texts = (segment.corrected_text or '').split()

        matcher = difflib.SequenceMatcher(None, word_texts, corrected_word_texts)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ('equal', 'replace'):
                original_slice = segment_words[i1:i2]
                corrected_slice = corrected_word_texts[j1:j2]

                for index, word in enumerate(original_slice):
                    if index < len(corrected_slice):
                        word.corrected_word = corrected_slice[index]
                        word.is_correction_removed = False
                    else:
                        word.corrected_word = None
                        word.is_correction_removed = True

                    word.search_content = f"{word.corrected_word or ''} {(word.word if word.corrected_word != word.word else None) or ''}".strip()
                    word.last_modified_user = user
                    word.last_modified_date = now
                    words_to_bulk_update.append(word)
            elif tag == 'delete':
                for word in segment_words[i1:i2]:
                    word.corrected_word = None
                    word.is_correction_removed = True
                    word.search_content = f"{word.corrected_word or ''} {(word.word if word.corrected_word != word.word else None) or ''}".strip()
                    word.last_modified_user = user
                    word.last_modified_date = now
                    words_to_bulk_update.append(word)
            elif tag == 'insert':
                pass

    if words_to_bulk_update:
        Word.objects.bulk_update(
            words_to_bulk_update,
            ['corrected_word', 'is_correction_removed', 'search_content', 'last_modified_user', 'last_modified_date'],
            batch_size=1000
        )
