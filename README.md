# 회의 관리

<img alt="Python" src ="https://img.shields.io/badge/Python-3776AB.svg?&style=for-the-badge&logo=Python&logoColor=white"/>
<img alt="Django" src ="https://img.shields.io/badge/Django-092E20.svg?&style=for-the-badge&logo=Django&logoColor=white"/>

<img alt="Pytorch" src ="https://img.shields.io/badge/Pytorch-EE4C2C.svg?&style=for-the-badge&logo=Pytorch&logoColor=white"/>
<img alt="Hugging Face" src ="https://img.shields.io/badge/Hugging%20Face-FFD21E.svg?&style=for-the-badge&logo=Hugging%20Face&logoColor=black"/>
<img alt="Google Gemini" src ="https://img.shields.io/badge/Google%20Gemini-8E75B2.svg?&style=for-the-badge&logo=Google%20Gemini&logoColor=white"/>

<img alt="Bootstrap" src ="https://img.shields.io/badge/Bootstrap-7952B3.svg?&style=for-the-badge&logo=Bootstrap&logoColor=white"/>

<img alt="PostgreSQL" src ="https://img.shields.io/badge/PostgreSQL-4169E1.svg?&style=for-the-badge&logo=PostgreSQL&logoColor=white"/>

<img alt="FFmpeg" src ="https://img.shields.io/badge/FFmpeg-007808.svg?&style=for-the-badge&logo=FFmpeg&logoColor=white"/>

---

## 📖 프로젝트 소개 및 목적

### 선정 배경
- 사내, 프로젝트 등 회의 시 회의록 작성에 시간 소요
- 세부 내용이 기억나지 않거나, 비참여자에게 내용 전달 시 정보 누락 또는 잘못된 정보 전달 가능성이 존재하고, 참여자 간 기억하는 내용이 다름 등의 문제점
 
### 수행방안 및 목표
- 회의실 예약, 기록, 텍스트 변환 및 교정, 요약, 검색, 공유 등 기능을 제공하는 프로토타입 개발
- Python3 Django 기반 퍼블릭 클라우드 API 사용(가능한 부분은 직접 모델 구축)

### 기대효과
- 회의록 작성 시간 단축
- 다시 듣기, 내용 검색, 공유 등 정보 활용 증대(사내시스템, PMS 등 연계)

---

## 🚀 설치 및 실행 방법

### 개발 환경(Mac 기준)

#### FFmpeg
```shell
$ brew install pkg-config ffmpeg@6 sox libsndfile1
```

#### [python3](https://www.python.org/downloads/)
```shell
$ brew install python@3.11
$ cd /app/django-meeting
$ python3.11 -m venv .venv
$ source .venv/bin/activate
$ python3 --version
Python 3.11.14

$ git clone https://github.com/give928/django-meeting-prototype.git
$ pip install av==12.3.0 --no-deps
$ pip install -r requirements_mac.txt
```

#### PostgreSQL(docker)
```shell
$ docker-compose -f docker/postgres/dev/docker-compose.yml up -d
```

#### [Django](https://www.djangoproject.com/)
- Django SECRET_KEY 생성
  ```sheel
  $ python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
  '%^7#p!@q8...'
  ```
- 환경 변수 설정 파일 .env 생성(.env.sample 참고)
  ```shell
  $ cp .env.sample .env
  $ vi .env
  # .env
  
  # Django SECRET_KEY
  SECRET_KEY="django-insecure-%^7#p!@q8..."

  # Library Path - FFmpeg
  DYLD_LIBRARY_PATH=/opt/homebrew/Cellar/ffmpeg@6/6.1.4/lib
  
  # Database
  #DATABASE_URL=sqlite:///db.sqlite3
  DATABASE_HOST=127.0.0.1
  DATABASE_PORT=5432
  DATABASE_NAME=meeting_db
  DATABASE_USER=meeting_user
  DATABASE_PASSWORD=P@ssw0rd
  
  # Hugging Face token
  HF_TOKEN=hf_...
  
  # Gemini API key
  GEMINI_API_KEY=AI...
  
  DEBUG=True
  
  ALLOWED_HOSTS=*
  ```

- Database 마이그레이션
  ```shell
  $ python manage.py migrate
  ```

- Database 초기 데이터(Optional)
  ```shell
  $ python manage.py loaddata */fixtures/*.json
  ```

- Django 실행
  ```shell
  $ python manage.py qcluster
  $ python manage.py runserver
  ```

### 컨테이너 배포

#### Docker

```shell
$ docker-compose up --build -d
```

#### Database 마이그레이션

```shell
$ docker-compose exec django python manage.py migrate
```

#### (Optional)초기 데이터

```shell
$ docker-compose exec django python manage.py loaddata */fixtures/*.json
```

---

## 💻 사용 방법

1. 슈퍼유저 등록
   ```shell
   $ python manage.py createsuperuser
   Email:
   Username:
   Password: 
   Password (again): 
   Superuser created successfully.
   ```

2. 로그인
   > http://127.0.0.1 or http://127.0.0.1:8000
   > 관리자: http://127.0.0.1/admin/

---

## 🛠️ 주요 기능

- [x] 로그인
- [x] 회의실
- [x] 회의
  - [x] 예약
  - [x] 브라우저 녹음
  - [x] 녹음 파일 업로드
    - [x] WebM 파일 형식 변환
    - [ ] 녹음 파일이 여러개인 경우 파일 및 회의록 병합
  - [x] 비동기 큐 작업
    - [x] RDB
    - [ ] Redis
    - [ ] MQ
  - [x] 텍스트 변환
    - [x] Faster-Whisper
      - 오디오 파일을 텍스트로 변환
      - 텍스트를 시간대별로 나눈 세그먼트(시작시간, 종료시간, 텍스트)를 생성
      - 언어 감지
    - [x] Wav2Vec2
      - 세그먼트 내의 개별 단어마다 정확한 시작시간, 종료시간을 재계산하고 할당
      - 화자 분리 결과를 텍스트에 매핑할 때 정확도를 높이는 데 필수
  - [x] 화자 분리
    - [x] Pyannote Audio
      - 누가 언제 말했는지를 감지
      - 텍스트 내용과는 무관, 오디오 신호만을 분석
      - 시간대별 화자 레이블을 생성
      - [Hugging Face](https://huggingface.co/)
        - 토큰 발급: [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
          ```shell
          $ export HF_TOKEN="hf_xxxxxxxxxxxxx"
          ```
        - 사용자 약관 동의
          - [Pyannote 3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
          - [Pyannote 3.0](https://huggingface.co/pyannote/speaker-diarization-3.0)
    - [ ] 화자 식별
      - Hybrid Recommender System
        1. 후보 생성: Rule-based
        2. 점수 계산: Contents-based 
        3. 점수 보정: Collaborative Filtering 
        4. 화자 식별
          - 확률(랭킹) 기반 화자 자동 매핑
          - 정답 수동 수정 → 학습 데이터로 재사용
  - [x] 교정
    - [x] Gemini 3 Flash Preview
  - [X] 요약
    - [x] Gemini 3 Flash Preview
    - 시스템 지침
      ```
      당신은 회의록 전사 기록을 교정하고 내용을 구조화하여 공식 회의록을 작성하는 전문가입니다. 
      제공된 데이터를 분석하여 반드시 **지정된 JSON 스키마 형식**으로만 응답해야 합니다.
      
      **[핵심 원칙]**
      1. **정확성:** 원본의 의미를 왜곡하지 않고 정확하게 교정해야 합니다.
      2. **데이터 무결성:** 결과의 'corrected_segments' 리스트에 있는 'original_segment_id'는 입력된 원본 ID와 반드시 일치해야 합니다.
      3. **가독성 (문단 분리):** 텍스트 교정 시, 다음 기준에 따라 적극적으로 문단을 분리하고 개행 문자('\\n')를 사용하십시오.
         - 화자가 바뀌거나 주제가 전환될 때.
         - 하나의 문단에는 하나의 중심 생각만 담을 것.
      ```
    - 프롬프트
      ```
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
      ...
      ```
  - [x] 대화 포커스
    - [x] 재생 시간 이동하면 대화 포커스
    - [x] 대화 클릭하면 재생 시간 이동
  - [X] 검색
    - [x] ~~데이터베이스 인덱스 (B-Tree)~~
    - [x] PostgreSQL Trigram (GIN) 인덱스
      - case-insensitive 검색 성능 👍
      - trigram_similar 오타 교정 검색
    - [ ] Elasticsearch
      - 대규모 성능 👍
      - 복잡/오타교정/유사단어 검색
  - [ ] 공유

---

## 📝 라이선스

This project is [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0) licensed.