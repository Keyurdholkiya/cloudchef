#!/bin/sh
set -eu

python manage.py migrate --noinput

if [ "${SEED_DEMO:-false}" = "true" ]; then
  python manage.py seed_demo
fi

exec "$@"
