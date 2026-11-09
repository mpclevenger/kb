#!/bin/sh
# TRAC container start-up. Runs every time the container starts, then starts the web server.
#
# 1. Brings the database up to date.
# 2. Creates the admin account the first time (TRAC_ADMIN_USER and TRAC_ADMIN_PASSWORD).
# 3. Adds any new topics and platforms from the starting lists.
# 4. Checks the content files and, if they pass, syncs them into the site.
#    With ALLOW_SELF_APPROVAL=true the changes are published straight away;
#    otherwise they arrive as proposed updates to approve in the site.
#    If the check or sync fails, the site still starts with its previous content
#    and the reason is written to the container log. Sample evidence rules arrive as drafts.
set -e
# The project folder: APP_DIR if set, otherwise the folder above this script.
cd "${APP_DIR:-$(dirname "$0")/..}"

if [ ! -d staticfiles ]; then
  echo "== Preparing the styling files (first start on this image)"
  python manage.py collectstatic --noinput
fi

echo "== Updating the database"
python manage.py migrate --noinput

if [ -z "$TRAC_ADMIN_USER" ]; then
  echo "== TRAC_ADMIN_USER is not set, so content is not synced. Set it to your admin username."
else
  if python manage.py shell -c "import sys; from django.contrib.auth import get_user_model as g; sys.exit(0 if g().objects.filter(username='$TRAC_ADMIN_USER').exists() else 1)"; then
    echo "== Admin account $TRAC_ADMIN_USER found"
  elif [ -n "$TRAC_ADMIN_PASSWORD" ]; then
    echo "== Creating admin account $TRAC_ADMIN_USER"
    DJANGO_SUPERUSER_USERNAME="$TRAC_ADMIN_USER" DJANGO_SUPERUSER_PASSWORD="$TRAC_ADMIN_PASSWORD" \
      DJANGO_SUPERUSER_EMAIL="${TRAC_ADMIN_EMAIL:-}" python manage.py createsuperuser --noinput
  else
    echo "== No account named $TRAC_ADMIN_USER yet. Set TRAC_ADMIN_PASSWORD once to create it."
  fi

  if python manage.py shell -c "import sys; from django.contrib.auth import get_user_model as g; sys.exit(0 if g().objects.filter(username='$TRAC_ADMIN_USER').exists() else 1)"; then
    echo "== Loading anything new from the starting topics and platforms"
    python manage.py seed_topics
    python manage.py seed_platforms

    echo "== Checking the content files"
    if python manage.py check_content; then
      PUBLISH=""
      case "$(echo "${ALLOW_SELF_APPROVAL:-false}" | tr 'A-Z' 'a-z')" in
        true) PUBLISH="--publish" ;;
      esac
      echo "== Syncing the content files into the site $PUBLISH"
      python manage.py sync_content --user "$TRAC_ADMIN_USER" $PUBLISH \
        || echo "!! Sync reported a problem (see above). The site will still start."
      # Sample evidence rules are examples to fill in, so they stay drafts until approved in the site.
      python manage.py seed_evidence_rules --user "$TRAC_ADMIN_USER" || true
    else
      echo "!! The content check found problems (see above). Nothing was synced; the site keeps its previous content."
    fi
  fi
fi

echo "== Starting the web server"
exec gunicorn config.wsgi --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_WORKERS:-3}" --worker-tmp-dir /dev/shm --log-file -
