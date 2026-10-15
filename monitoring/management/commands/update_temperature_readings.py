import random
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from monitoring.models import WaterQuality


MANILA = ZoneInfo('Asia/Manila')


def target_temperature(recorded_at):
    hour = timezone.localtime(recorded_at, MANILA).hour
    if hour >= 21 or hour < 6:
        return Decimal('24.00')
    if hour < 10:
        return Decimal('27.00')
    if hour < 17:
        return Decimal('30.00')
    return Decimal('28.00')


def create_database_backup(database_path):
    if str(database_path) == ':memory:' or not database_path.is_file():
        raise CommandError('A file-backed SQLite database is required for a backup.')

    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S%f')
    backup_path = database_path.with_name(f'{database_path.name}.{timestamp}.bak')
    try:
        with backup_path.open('xb'):
            pass
        with sqlite3.connect(database_path) as source:
            with sqlite3.connect(backup_path) as destination:
                source.backup(destination)
                result = destination.execute('PRAGMA integrity_check').fetchone()[0]
                if result != 'ok':
                    raise CommandError(f'SQLite backup integrity check failed: {result}')
    except Exception:
        backup_path.unlink(missing_ok=True)
        raise
    return backup_path


class Command(BaseCommand):
    help = 'Update water-quality temperatures to realistic Manila time-of-day values.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show how many readings fall in each time period without changing data.',
        )
        parser.add_argument(
            '--seed', type=int, default=None,
            help='Seed the random variation for repeatable results.',
        )

    def handle(self, *args, **options):
        if connection.vendor != 'sqlite':
            raise CommandError('This command requires the configured SQLite database.')

        readings = list(
            WaterQuality.objects.only('id', 'recorded_at').iterator(chunk_size=1000)
        )
        if not readings:
            self.stdout.write('No water-quality readings found; nothing to update.')
            return

        if options['dry_run']:
            periods = {24: 0, 27: 0, 30: 0, 28: 0}
            for reading in readings:
                periods[int(target_temperature(reading.recorded_at))] += 1
            self.stdout.write(
                f'Dry run: {len(readings)} readings; period counts (24/27/30/28°C): '
                f'{periods[24]}/{periods[27]}/{periods[30]}/{periods[28]}.'
            )
            return

        database_path = Path(connection.settings_dict['NAME'])
        backup_path = create_database_backup(database_path)
        generator = random.Random(options['seed'])
        for reading in readings:
            base = target_temperature(reading.recorded_at)
            variation = Decimal(generator.randint(-50, 50)) / Decimal('100')
            reading.temperature = (base + variation).quantize(Decimal('0.01'))

        with transaction.atomic():
            WaterQuality.objects.bulk_update(readings, ['temperature'], batch_size=500)

        self.stdout.write(
            self.style.SUCCESS(
                f'Updated {len(readings)} temperature readings. Backup: {backup_path}'
            )
        )