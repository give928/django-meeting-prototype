import logging
import os

import torch
import whisperx
from pandas import DataFrame

logger = logging.getLogger(__name__)


class RecordingUtils:
    @staticmethod
    def transcribe(file_path):
        model = ModelHolder.get_model()
        return model.transcribe(file_path)

    @staticmethod
    def align(file_path, language_code, segments) -> dict:
        align_model, metadata = ModelHolder.get_align_model(language_code)
        return whisperx.align(segments, align_model, metadata, file_path, ModelHolder.get_device())

    @staticmethod
    def diarize(file_path) -> tuple[DataFrame, dict[str, list[float]] | None] | DataFrame:
        diarization_pipeline = ModelHolder.get_diarization_pipeline()
        return diarization_pipeline(file_path)

    @staticmethod
    def assign(aligned: dict, diarized: tuple[DataFrame, dict[str, list[float]] | None] | DataFrame) -> dict:
        result = whisperx.assign_word_speakers(diarized, aligned)
        result['speech_recognition_model_name'] = ModelHolder.get_model_name()
        result['align_model_name'] = ModelHolder.get_align_model_name()
        result['diarization_model_name'] = ModelHolder.get_diarization_model_name()
        return result


class ModelHolder:
    _MODEL = None
    _MODEL_NAME = 'Faster Whisper'
    _MODEL_SIZE = 'medium'  # base, small, large-v2
    _ALIGN_MODEL = None
    _ALIGN_MODEL_NAME = 'Wav2Vec2'
    _DIARIZATION_PIPELINE = None
    _DIARIZATION_MODEL_NAME = 'pyannote/speaker-diarization-3.1'
    _DEVICE = None

    @staticmethod
    def get_model():
        if ModelHolder._MODEL is None:
            ModelHolder._MODEL = whisperx.load_model(ModelHolder._MODEL_SIZE,
                                                     device=ModelHolder.get_device(),
                                                     compute_type="int8")
        return ModelHolder._MODEL

    @staticmethod
    def get_model_name():
        return f"{ModelHolder._MODEL_NAME}({ModelHolder._MODEL_SIZE})"

    @staticmethod
    def get_align_model(language_code):
        align_model, metadata = whisperx.load_align_model(
            language_code=language_code, device=ModelHolder.get_device()
        )
        return align_model, metadata

    @staticmethod
    def get_align_model_name():
        return ModelHolder._ALIGN_MODEL_NAME

    @staticmethod
    def get_diarization_pipeline():
        if ModelHolder._DIARIZATION_PIPELINE is None:
            token = ModelHolder.get_hf_token()

            from whisperx.diarize import DiarizationPipeline

            ModelHolder._DIARIZATION_PIPELINE = DiarizationPipeline(
                use_auth_token=token,
                device=ModelHolder.get_device()
            )

        return ModelHolder._DIARIZATION_PIPELINE

    @staticmethod
    def get_diarization_model_name():
        return ModelHolder._DIARIZATION_MODEL_NAME

    @staticmethod
    def get_hf_token():
        token = os.environ.get('HF_TOKEN')
        if not token:
            raise RuntimeError('HF_TOKEN environment variable is missing. It is required for pyannote.audio.')
        return token

    @staticmethod
    def get_device():
        if ModelHolder._DEVICE is None:
            # faster-whisper/ctranslate2가 mps를 지원하지 않음
            # Mac M 시리즈에서 성능 최적화는 'compute_type="int8"'로 간접적으로 처리
            # if torch.backends.mps.is_available():
            #     ModelHolder._DEVICE = 'mps'
            # else:
            #     ModelHolder._DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
            ModelHolder._DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
        return ModelHolder._DEVICE
