# 회의 공유

<img alt="Python" src ="https://img.shields.io/badge/Python-3776AB.svg?&style=for-the-badge&logo=Python&logoColor=white"/>
<img alt="Django" src ="https://img.shields.io/badge/Django-092E20.svg?&style=for-the-badge&logo=Django&logoColor=white"/>
<img alt="Google Cloud" src ="https://img.shields.io/badge/Google Cloud-4285F4.svg?&style=for-the-badge&logo=Google Cloud&logoColor=white"/>
<img alt="Google Gemini" src ="https://img.shields.io/badge/Google Gemini-8E75B2.svg?&style=for-the-badge&logo=Google Gemini&logoColor=white"/>

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
$ python3 --version
Python 3.13.5
```

#### [Django](https://www.djangoproject.com/)
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

$ python manage.py makemigrations rooms

$ python manage.py migrate rooms
```

---

## 💻 Usage

---

## 🛠️ Contents

- [x] 로그인
- [x] 회의실
- [ ] 회의
  - [ ] 예약
  - [ ] 녹음
  - [ ] 텍스트 변환
  - [ ] 교정
  - [ ] 요약
  - [ ] 검색
  - [ ] 공유

---

## 📝 License

This project is [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0) licensed.