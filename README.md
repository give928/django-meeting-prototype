# 회의 관리

<img alt="Python" src ="https://img.shields.io/badge/Python-3776AB.svg?&style=for-the-badge&logo=Python&logoColor=white"/>
<img alt="Django" src ="https://img.shields.io/badge/Django-092E20.svg?&style=for-the-badge&logo=Django&logoColor=white"/>

<img alt="Pytorch" src ="https://img.shields.io/badge/Pytorch-EE4C2C.svg?&style=for-the-badge&logo=Pytorch&logoColor=white"/>
<img alt="Hugging Face" src ="https://img.shields.io/badge/Hugging%20Face-FFD21E.svg?&style=for-the-badge&logo=Hugging%20Face&logoColor=black"/>
<img alt="Google Gemini" src ="https://img.shields.io/badge/Google%20Gemini-8E75B2.svg?&style=for-the-badge&logo=Google%20Gemini&logoColor=white"/>

<img alt="SQLite" src ="https://img.shields.io/badge/SQLite-003B57.svg?&style=for-the-badge&logo=SQLite&logoColor=white"/>

<img alt="Bootstrap" src ="https://img.shields.io/badge/Bootstrap-7952B3.svg?&style=for-the-badge&logo=Bootstrap&logoColor=white"/>

<img alt="FFmpeg" src ="https://img.shields.io/badge/FFmpeg-007808.svg?&style=for-the-badge&logo=FFmpeg&logoColor=white"/>
<img alt="Markdown" src ="https://img.shields.io/badge/Markdown-000000.svg?&style=for-the-badge&logo=Markdown&logoColor=white"/>

---

## 🗝️ Description

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

## 🚀 Install and Run

#### [python3](https://www.python.org/downloads/)
```shell
$ brew install pkg-config ffmpeg@6 sox libsndfile1
$ export DYLD_LIBRARY_PATH="/opt/homebrew/Cellar/ffmpeg@6/6.1.4/lib"

$ brew install python@3.11
$ cd {프로젝트루트:/app/meeting}
$ python3.11 -m venv .venv
$ source .venv/bin/activate
$ python3 --version
Python 3.11.14
$ pip install av==12.3.0 --no-deps
$ pip install -r requirements.txt
```

#### [Django](https://www.djangoproject.com/)
- Environment
  ```shell
  $ vi .env

  # 라이브러리 패스 - FFmpeg
  DYLD_LIBRARY_PATH=/opt/homebrew/Cellar/ffmpeg@6/6.1.4/lib
  
  # Database
  #DATABASE_URL=postgres://user:password@host:port/dbname
  DATABASE_URL=sqlite:///db.sqlite3
  
  # Hugging Face token
  HF_TOKEN="..."
  
  # Gemini API key
  GEMINI_API_KEY="..."
  
  DEBUG=True
  
  ALLOWED_HOSTS=.localhost,127.0.0.1
  ```

- Install Django
  ```shell
  $ python -m pip install Django
  ```
  
  ```shell
  $ python manage.py startproject config
  
  $ python manage.py startapp accounts
  
  $ python manage.py makemigrations
  Migrations for 'accounts':
    accounts/migrations/0001_initial.py
      + Create model User
      + Create model Department
  
  $ python manage.py migrate
  Operations to perform:
    Apply all migrations: accounts, admin, auth, contenttypes, sessions
  Running migrations:
    Applying contenttypes.0001_initial... OK
    Applying contenttypes.0002_remove_content_type_name... OK
    Applying auth.0001_initial... OK
    Applying auth.0002_alter_permission_name_max_length... OK
    Applying auth.0003_alter_user_email_max_length... OK
    Applying auth.0004_alter_user_username_opts... OK
    Applying auth.0005_alter_user_last_login_null... OK
    Applying auth.0006_require_contenttypes_0002... OK
    Applying auth.0007_alter_validators_add_error_messages... OK
    Applying auth.0008_alter_user_username_max_length... OK
    Applying auth.0009_alter_user_last_name_max_length... OK
    Applying auth.0010_alter_group_name_max_length... OK
    Applying auth.0011_update_proxy_permissions... OK
    Applying auth.0012_alter_user_first_name_max_length... OK
    Applying accounts.0001_initial... OK
    Applying admin.0001_initial... OK
    Applying admin.0002_logentry_remove_auto_add... OK
    Applying admin.0003_logentry_add_action_flag_choices... OK
    Applying sessions.0001_initial... OK
  
  $ python manage.py createsuperuser
  Email: give928@gmail.com
  Username: 김주호
  Password: 
  Password (again): 
  Superuser created successfully.
  
  $ python manage.py loaddata accounts/fixtures/*
  Installed 87 object(s) from 3 fixture(s)
  
  $ mkdir logs
  
  $ pip install django-bootstrap5
  
  $ python manage.py startapp common
  
  $ python manage.py startapp rooms
  
  $ python manage.py makemigrations rooms
  Migrations for 'rooms':
    rooms/migrations/0001_initial.py
      + Create model Room
  
  $ python manage.py migrate rooms
  Operations to perform:
    Apply all migrations: rooms
  Running migrations:
    Applying rooms.0001_initial... O
  
  $ python manage.py loaddata rooms/fixtures/*
  Installed 6 object(s) from 1 fixture(s)
  
  $ pip install django-mptt
  Collecting django-mptt
    Downloading django_mptt-0.18.0-py3-none-any.whl.metadata (5.3 kB)
  Collecting django-js-asset (from django-mptt)
    Downloading django_js_asset-3.1.2-py3-none-any.whl.metadata (6.4 kB)
  Requirement already satisfied: django>=4.2 in ./.venv/lib/python3.13/site-packages (from django-js-asset->django-mptt) (5.2.4)
  Requirement already satisfied: asgiref>=3.8.1 in ./.venv/lib/python3.13/site-packages (from django>=4.2->django-js-asset->django-mptt) (3.9.1)
  Requirement already satisfied: sqlparse>=0.3.1 in ./.venv/lib/python3.13/site-packages (from django>=4.2->django-js-asset->django-mptt) (0.5.3)
  Downloading django_mptt-0.18.0-py3-none-any.whl (120 kB)
  Downloading django_js_asset-3.1.2-py3-none-any.whl (5.9 kB)
  Installing collected packages: django-js-asset, django-mptt
  Successfully installed django-js-asset-3.1.2 django-mptt-0.18.0
  
  $ pip install django-bootstrap-datepicker-plus
  
  $ python manage.py startapp reservations
  
  $ python manage.py makemigrations reservations
  Migrations for 'reservations':
    reservations/migrations/0001_initial.py
      + Create model Attendee
      + Create model Reservation
      + Add field reservation to attendee
      + Create index idx_reservation_01 on field(s) room, start_datetime of model reservation
      ~ Alter unique_together for attendee (1 constraint(s))
  
  $ python manage.py migrate reservations
  Operations to perform:
    Apply all migrations: reservations
  Running migrations:
    Applying reservations.0001_initial... OK
  
  $ python manage.py startapp meetings
  
  $ python manage.py makemigrations meetings
 Migrations for 'meetings':
  meetings/migrations/0001_initial.py
    + Create model Attendee
    + Create model Meeting
    + Add field meeting to attendee
    + Create model Recording
    + Create model Speaker
    + Create model SpeechRecognition
    + Create model Segment
    + Add field latest_speech_recognition to recording
    + Create model Summarization
    + Add field latest_summarization to recording
    + Create model Word
    + Create index idx_meeting_01 on field(s) start_datetime, end_datetime of model meeting
    ~ Alter unique_together for attendee (1 constraint(s))
    + Create index idx_speech_recognition_01 on field(s) task_status_code of model speechrecognition
    + Create index idx_speech_recognition_02 on field(s) task_step_code of model speechrecognition
    + Create index idx_summarization_01 on field(s) task_status_code of model summarization
    + Create index idx_word_01 on field(s) search_content of model word
  
  $ python manage.py migrate meetings
  Operations to perform:
    Apply all migrations: meetings
  Running migrations:
    Applying meetings.0001_initial... OK
  ```

---

## 💻 Usage

---

## 🛠️ Contents

- [x] 로그인
- [x] 회의실
- [x] 회의
  - [x] 예약
  - [x] 브라우저 녹음
  - [x] 녹음 파일 업로드
    - [x] WebM 파일 형식 변환
    - [ ] 녹음 파일이 여러개인 경우 파일 및 회의록 병합
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
    - [x] Gemini 2.5 Flash
  - [X] 요약
    - [x] Gemini 2.5 Flash
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
    - [x] 데이터베이스 인덱스 (B-Tree)
    - [ ] PostgreSQL Trigram (GIN) 인덱스
      - case-insensitive 검색 성능 👍
    - [ ] Elasticsearch
      - 복잡/오타/유사단어 검색 가능, 대규모 성능 👍
  - [ ] 공유

---

## 📝 License

This project is [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0) licensed.