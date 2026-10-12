"""Create clearly labeled simulated water-quality history for demonstrations."""
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from monitoring.models import WaterQuality


DEMO_MARKER = '[SIMULATED DEMO - NOT A POTABILITY TEST]'


class Command(BaseCommand):
    help = 'Create simulated water-quality readings every 10 minutes for a date range.'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=date.fromisoformat, default=date(2026, 9, 22))
        parser.add_argument('--end', type=date.fromisoformat, default=date(2026, 10, 22))
        parser.add_argument('--interval-minutes', type=int, default=10)

    def handle(self, *args, **options):
        start_date = options['start']
        end_date = options['end']
        interval = options['interval_minutes']
        if end_date < start_date:
            raise ValueError('End date must be on or after start date.')
        if interval <= 0 or 1440 % interval:
            raise ValueError('Interval must be a positive divisor of 1440 minutes.')

        tz = timezone.get_current_timezone()
        start_at = timezone.make_aware(datetime.combine(start_date, time.min), tz)
        end_at = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min), tz)
        existing_by_slot = {}
        existing_rows = WaterQuality.objects.filter(
            recorded_at__gte=start_at,
            recorded_at__lt=end_at,
            notes__startswith=DEMO_MARKER,
        )
        for row in existing_rows:
            local_time = timezone.localtime(row.recorded_at, tz)
            slot_minute = local_time.minute - local_time.minute % interval
            slot_time = local_time.replace(minute=slot_minute, second=0, microsecond=0)
            existing_by_slot[slot_time] = row

        records = []
        adjusted_rows = []
        unchanged_count = 0
        cursor = start_at
        while cursor < end_at:
            timestamp_rng = random.Random(f'{cursor.isoformat()}-timestamp')
            recorded_at = cursor + timedelta(seconds=timestamp_rng.randint(1, 59))
            existing = existing_by_slot.get(cursor)
            if existing is None:
                rng = random.Random(cursor.isoformat())
                records.append(WaterQuality(
                    ph=Decimal(str(round(rng.uniform(7.0, 7.6), 2))),
                    tds=Decimal(str(round(rng.uniform(90, 180), 2))),
                    turbidity=Decimal(str(round(rng.uniform(0.2, 0.9), 2))),
                    temperature=Decimal(str(round(rng.uniform(24, 29), 2))),
                    flow_rate=Decimal(str(round(rng.uniform(0, 12), 2))),
                    water_pressure=Decimal(str(round(rng.uniform(1.5, 3.0), 2))),
                    water_level=Decimal(str(round(rng.uniform(25, 100), 2))),
                    recorded_at=recorded_at,
                    notes=f'{DEMO_MARKER} Synthetic values; laboratory testing is required to establish potability.',
                ))
            elif existing.recorded_at != recorded_at:
                existing.recorded_at = recorded_at
                adjusted_rows.append(existing)
            else:
                unchanged_count += 1
            cursor += timedelta(minutes=interval)

        with transaction.atomic():
            if adjusted_rows:
                WaterQuality.objects.bulk_update(adjusted_rows, ['recorded_at'])
            for record in records:
                record.save()

        self.stdout.write(self.style.SUCCESS(
            f'Created {len(records)} simulated readings and adjusted '
            f'{len(adjusted_rows)} timestamps; {unchanged_count} were already up to date.'
        ))
