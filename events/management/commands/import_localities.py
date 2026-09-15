import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import Locality


class Command(BaseCommand):
    help = 'Import Japanese locality data from Geolonia japanese-addresses CSV.'

    def add_arguments(self, parser):
        parser.add_argument('source', type=Path, help='Path to japanese-addresses latest.csv')

    def handle(self, *args, **options):
        source = options['source']
        if not source.is_file():
            raise CommandError(f'File not found: {source}')

        prefectures = defaultdict(lambda: [0, 0, 0.0, 0.0])
        municipalities = defaultdict(lambda: [0, 0, 0.0, 0.0])
        locality_count = 0

        with transaction.atomic():
            Locality.objects.all().delete()
            batch = []

            with source.open(encoding='utf-8', newline='') as file:
                reader = csv.reader(file)
                next(reader, None)
                for row in reader:
                    if len(row) < 14:
                        continue

                    prefecture_code, prefecture = row[0], row[1]
                    municipality_code, municipality = row[4], row[5]
                    town, koaza = row[8], row[11]
                    if not town:
                        continue

                    try:
                        latitude = float(row[12])
                        longitude = float(row[13])
                    except ValueError:
                        continue

                    full_name = f'{prefecture}{municipality}{town}{koaza}'
                    name = f'{town}{koaza}'
                    source_value = '|'.join((municipality_code, town, koaza, row[12], row[13]))
                    batch.append(
                        Locality(
                            source_key=hashlib.sha256(source_value.encode()).hexdigest(),
                            name=name,
                            full_name=full_name,
                            detail=f'{prefecture}{municipality}',
                            kind='town',
                            latitude=latitude,
                            longitude=longitude,
                        )
                    )
                    locality_count += 1

                    prefecture_stats = prefectures[prefecture_code]
                    prefecture_stats[0] += 1
                    prefecture_stats[1] = prefecture
                    prefecture_stats[2] += latitude
                    prefecture_stats[3] += longitude

                    municipality_stats = municipalities[municipality_code]
                    municipality_stats[0] += 1
                    municipality_stats[1] = (prefecture, municipality)
                    municipality_stats[2] += latitude
                    municipality_stats[3] += longitude

                    if len(batch) >= 1000:
                        Locality.objects.bulk_create(batch, batch_size=1000)
                        batch.clear()

            if batch:
                Locality.objects.bulk_create(batch, batch_size=1000)

            summary_rows = []
            for prefecture_code, (count, prefecture, latitude, longitude) in prefectures.items():
                summary_rows.append(
                    Locality(
                        source_key=f'prefecture:{prefecture_code}',
                        name=prefecture,
                        full_name=prefecture,
                        detail='Prefecture',
                        kind='prefecture',
                        latitude=latitude / count,
                        longitude=longitude / count,
                    )
                )
            for municipality_code, (count, names, latitude, longitude) in municipalities.items():
                prefecture, municipality = names
                summary_rows.append(
                    Locality(
                        source_key=f'municipality:{municipality_code}',
                        name=municipality,
                        full_name=f'{prefecture}{municipality}',
                        detail=prefecture,
                        kind='municipality',
                        latitude=latitude / count,
                        longitude=longitude / count,
                    )
                )
            Locality.objects.bulk_create(summary_rows, batch_size=1000)

        self.stdout.write(
            self.style.SUCCESS(
                f'Imported {locality_count} localities and {len(summary_rows)} area summaries.'
            )
        )
