#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput 2>/dev/null || true

exec "$@"
