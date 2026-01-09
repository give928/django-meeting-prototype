#!/bin/bash

# 에러 발생 시 즉시 중단
set -e

echo "Starting deployment tasks..."

# 1. 정적 파일 수집
echo "Collecting static files..."
python manage.py collectstatic --noinput

# 2. 데이터베이스 마이그레이션
echo "Applying database migrations..."
python manage.py migrate --noinput

# 3. Gunicorn 실행 (Dockerfile의 CMD 대신 실행)
echo "Starting Gunicorn..."
exec "$@"