#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput 2>/dev/null || true

# Auto-create superuser if ADMIN_USER, ADMIN_EMAIL, and ADMIN_PASSWORD are set
if [ -n "$ADMIN_USER" ] && [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$ADMIN_USER').exists():
    User.objects.create_superuser('$ADMIN_USER', '$ADMIN_EMAIL', '$ADMIN_PASSWORD')
    print('Superuser $ADMIN_USER created.')
else:
    print('Superuser $ADMIN_USER already exists.')
"
fi

exec "$@"
