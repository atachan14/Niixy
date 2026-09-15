# NiiMap v0.1 Deployment

## Target Architecture

* Koyeb: Django application hosting
* Neon: PostgreSQL database
* Geolonia: Map display

## Production Settings

Set these environment variables in Koyeb. Do not commit their values.

* `DJANGO_SECRET_KEY`: a long, random secret
* `DJANGO_DEBUG`: `False`
* `DJANGO_ALLOWED_HOSTS`: `{{ KOYEB_PUBLIC_DOMAIN }}`
* `DJANGO_CSRF_TRUSTED_ORIGINS`: `https://{{ KOYEB_PUBLIC_DOMAIN }}`
* `DATABASE_URL`: Neon connection string, including its SSL options
* `GEOLONIA_API_KEY`: production API key with the Koyeb domain allowed

## Koyeb Commands

Build command:

```text
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

Run command:

```text
python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

Configure Koyeb's health check to use `/healthz/`.

## First Database Setup

After the first deployment, apply migrations, create an Admin user, and import the station master into Neon.

```text
python manage.py createsuperuser
python manage.py import_stations data/raw/N02-25_GML.zip
```

The station ZIP is intentionally ignored by Git. Run the import against the production `DATABASE_URL`; do not commit the source ZIP or database credentials.
