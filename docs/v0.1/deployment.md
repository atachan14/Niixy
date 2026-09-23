# NiiMap v0.1 Deployment

## Target Architecture

* Vercel: Django application hosting
* Neon: PostgreSQL database
* Geolonia: Map display

## Database Selection

Supabase を最初の候補として検討したが、無料枠では一定期間アクセスのない Project が停止する運用だった。開発休止後にポートフォリオとして公開URLを確認する際、DB再開を忘れるリスクを避けるため、無料で扱いやすい PostgreSQL として Neon を採用した。

Neon Project はシンガポールリージョンに作成し、Vercel の `DATABASE_URL` から接続する。Neon や各サービスの無料枠・休止条件は将来変わり得るため、再検討時には公式ドキュメントを確認する。

## Production Settings

Set these environment variables in Vercel. Do not commit their values.

* `DJANGO_SECRET_KEY`: a long, random secret
* `DJANGO_DEBUG`: `False`
* `DJANGO_ALLOWED_HOSTS`: `.vercel.app`
* `DATABASE_URL`: Neon connection string, including its SSL options
* `GEOLONIA_API_KEY`: production API key with the Vercel domain allowed

## Vercel Commands

Vercel detects `manage.py`, serves static files automatically, and runs the production migration command defined in `vercel.json`.

## First Database Setup

After the first deployment, create an Admin user and import the location masters into Neon.

```text
python manage.py createsuperuser
python manage.py import_stations data/raw/N02-25_GML.zip
python manage.py import_localities data/raw/japanese-addresses-latest.csv
```

The station ZIP and locality CSV are intentionally ignored by Git. Run imports against the production `DATABASE_URL`; do not commit source data or database credentials. The locality CSV is downloaded from Geolonia japanese-addresses and attributed in the application under CC BY 4.0.

## Local Development

Create a local `.env` from `.env.example` and set `DATABASE_URL` to the Neon connection string. `runserver`, migrations, and management commands then use the same database as the deployed application.

`python manage.py test` always uses an in-memory SQLite database, even when `.env` contains `DATABASE_URL`. Test data never reaches Neon.
