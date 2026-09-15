import json
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import Station


class Command(BaseCommand):
    help = '国土数値情報の鉄道 GeoJSON から駅データを取り込みます。'

    def add_arguments(self, parser):
        parser.add_argument('source', type=Path, help='N02-xx_GML.zip のパス')

    def handle(self, *args, **options):
        source = options['source']
        if not source.is_file():
            raise CommandError(f'ファイルが見つかりません: {source}')

        with zipfile.ZipFile(source) as archive:
            station_files = [
                name for name in archive.namelist()
                if name.endswith('_Station.geojson') and '/UTF-8/' in name
            ]
            if len(station_files) != 1:
                raise CommandError('駅 GeoJSON を ZIP 内に見つけられませんでした。')
            data = json.loads(archive.read(station_files[0]).decode('utf-8'))

        stations = []
        imported_codes = set()
        for feature in data['features']:
            properties = feature['properties']
            station_code = properties['N02_005c']
            if station_code in imported_codes:
                continue
            imported_codes.add(station_code)
            coordinates = feature['geometry']['coordinates']
            longitude = sum(point[0] for point in coordinates) / len(coordinates)
            latitude = sum(point[1] for point in coordinates) / len(coordinates)
            stations.append(
                Station(
                    station_code=station_code,
                    group_code=properties['N02_005g'],
                    name=properties['N02_005'],
                    line_name=properties['N02_003'],
                    operator_name=properties['N02_004'],
                    latitude=latitude,
                    longitude=longitude,
                )
            )

        with transaction.atomic():
            Station.objects.all().delete()
            Station.objects.bulk_create(stations, batch_size=1000)
        self.stdout.write(self.style.SUCCESS(f'{len(stations)}駅を取り込みました。'))
