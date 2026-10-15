"""Create clearly labeled simulated water-quality history for demonstrations."""
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from monitoring.models import WaterQuality


DEMO_MARKER = '[SIMULATED DEMO - NOT A POTABILITY TEST]'
MEASUREMENT_LIMITS = {
    'ph': (700, 760, 5),
    'tds': (9000, 18000, 150),
    'turbidity': (20, 90, 3),
    'flow_rate': (0, 1200, 30),
    'water_pressure': (150, 300, 5),
    'water_level': (2500, 10000, 30),
}


def next_measurements(cursor, previous):
    rng = random.Random(f'{cursor.isoformat()}-measurements')
    values = {}
    for field, (minimum, maximum, max_step) in MEASUREMENT_LIMITS.items():
        previous_value = previous.get(field) if previous else None
        if previous_value is None:
            value = rng.randint(minimum, maximum)
        else:
            value = int(previous_value * 100) + rng.randint(-max_step, max_step)
            if value < minimum:
                value = minimum + (minimum - value)
            elif value > maximum:
                value = maximum - (value - maximum)
            value = min(max(value, minimum), maximum)
        values[field] = Decimal(value) / Decimal('100')
    return values


class Command(BaseCommand):
    help = 'Create simulated water-quality readings at a configurable nominal interval.'

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
        previous_measurements = None
        cursor = start_at
        while cursor < end_at:
            timestamp_rng = random.Random(f'{cursor.isoformat()}-timestamp')
            max_jitter_seconds = max(1, interval * 60 // 3)
            recorded_at = cursor + timedelta(
                seconds=timestamp_rng.randint(1, max_jitter_seconds)
            )
            measurements = next_measurements(cursor, previous_measurements)
            existing = existing_by_slot.get(cursor)
            if existing is None:
                local_hour = timezone.localtime(recorded_at, tz).hour
                if local_hour >= 21 or local_hour < 6:
                    temperature_base = 24
                elif local_hour < 10:
                    temperature_base = 27
                elif local_hour < 17:
                    temperature_base = 30
                else:
                    temperature_base = 28
                temperature_rng = random.Random(f'{cursor.isoformat()}-temperature')
                records.append(WaterQuality(
                    **measurements,
                    temperature=Decimal(temperature_base) + (
                        Decimal(temperature_rng.randint(-50, 50)) / Decimal('100')
                    ),
                    recorded_at=recorded_at,
                    notes=f'{DEMO_MARKER} Synthetic values; laboratory testing is required to establish potability.',
                ))
            else:
                changed = existing.recorded_at != recorded_at
                existing.recorded_at = recorded_at
                for field, value in measurements.items():
                    if getattr(existing, field) != value:
                        setattr(existing, field, value)
                        changed = True
                if changed:
                    adjusted_rows.append(existing)
                else:
                    unchanged_count += 1
            previous_measurements = measurements
            cursor += timedelta(minutes=interval)

        with transaction.atomic():
            if adjusted_rows:
                WaterQuality.objects.bulk_update(
                    adjusted_rows,
                    ['recorded_at', *MEASUREMENT_LIMITS],
                )
            for record in records:
                record.save()

        self.stdout.write(self.style.SUCCESS(
            f'Created {len(records)} simulated readings and adjusted '
            f'{len(adjusted_rows)} timestamps; {unchanged_count} were already up to date.'
        ))
