#!/usr/bin/env bash
set -e

# ---------- manage.py 위치 자동 탐색 ----------
APP_DIR=""
if [ -f "/app/manage.py" ]; then
  APP_DIR="/app"
elif [ -f "/app/cms/manage.py" ]; then
  APP_DIR="/app/cms"
else
  FOUND=$(find /app -maxdepth 3 -name "manage.py" | head -n 1 || true)
  if [ -n "$FOUND" ]; then
    APP_DIR="$(dirname "$FOUND")"
  else
    echo "❌ manage.py를 찾지 못했습니다. 프로젝트 루트를 확인하세요."
    exit 1
  fi
fi
echo "📁 Django app dir: $APP_DIR"

# ---------- DB 대기 ----------
if [ -n "${POSTGRES_HOST}" ]; then
  echo "⏳ Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT:-5432}..."
  until python - <<'PY'
import os, socket
h=os.getenv("POSTGRES_HOST","db"); p=int(os.getenv("POSTGRES_PORT","5432"))
s=socket.socket()
try: s.connect((h,p)); print("✅ PostgreSQL is up.")
except Exception as e: print("❌ Not ready:", e); exit(1)
finally: s.close()
PY
  do sleep 1; done
fi

# ---------- 마이그레이션 & 서버 ----------
cd "$APP_DIR"
python manage.py migrate --noinput
exec python manage.py runserver 0.0.0.0:8000
# 운영시:
# exec gunicorn config.wsgi:application --chdir "$APP_DIR" --bind 0.0.0.0:8000 --workers 3
