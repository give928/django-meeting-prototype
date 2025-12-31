# Dockerfile

FROM python:3.11-slim

# 파이썬 로그 즉시 출력
ENV PYTHONUNBUFFERED=1
ENV PIP_PREFER_BINARY=1
# FFmpeg 시스템 라이브러리 패스 설정
ENV LD_LIBRARY_PATH="/usr/local/lib:/usr/lib/aarch64-linux-gnu:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH}"

# 필수 시스템 패키지 및 ffmpeg 설치
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    pkg-config \
    build-essential \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    libpq-dev \
    gcc \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN ldconfig

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 설치
RUN pip install --upgrade pip setuptools wheel

RUN pip install "numpy<2.0"

COPY requirements_container.txt .
RUN pip install --no-cache-dir -r requirements_container.txt

# 텍스트 분절을 위한 데이터(punkt) 다운로드
RUN python -m nltk.downloader punkt

# WhisperX와 호환되는 "Golden Combination" 강제 재설치
RUN pip install "av==12.3.0" --only-binary=:all: --force-reinstall
RUN pip install "faster-whisper==1.0.3" --no-deps --force-reinstall
RUN pip install "git+https://github.com/m-bain/whisperX.git@v3.3.1" --no-deps --force-reinstall
# WhisperX 3.3.1 asr.py에서 faster-whisper 1.0.3에서 사라진 multilingual 인자를 기본 값으로 던지는 버전 호환 문제 해결을 위해 소스 코드 삭제
RUN sed -i '/"multilingual":/d' /usr/local/lib/python3.11/site-packages/whisperx/asr.py

RUN pip install gunicorn

# 소스 코드 복사
COPY . .

# 정적 파일 수집 (배포용)
# RUN python manage.py collectstatic --noinput

# Gunicorn 실행
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]