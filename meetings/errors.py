from typing import Optional


class GeminiApiError(Exception):
    def __init__(
            self,
            message: str,
            generative_ai_model_name: Optional[str] = None,
            exception: Optional[Exception] = None
    ):
        self.message = (
            f"Gemini API 호출 중 예외가 발생했어요 (모델: {generative_ai_model_name}, 원인: {message if message else '알 수 없음'})"
        )
        self.generative_ai_model_name = generative_ai_model_name
        self.exception = exception
        super().__init__(message)
