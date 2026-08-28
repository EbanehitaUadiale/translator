#!/usr/bin/env bash
# Render runs this on every deploy. Any non-zero exit fails the deploy, which is
# what we want -- a half-migrated app serving traffic is worse than no deploy.
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate
