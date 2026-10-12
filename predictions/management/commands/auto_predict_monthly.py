"""
Auto-run next-month ML prediction (once per day).

Usage:
  python manage.py auto_predict_monthly
  python manage.py auto_predict_monthly --force

Windows Task Scheduler example (daily 6:00 AM):
  Program:  C:\\...\\Capstone\\venv\\Scripts\\python.exe
  Args:     manage.py auto_predict_monthly
  Start in: C:\\...\\Capstone
"""
from django.core.management.base import BaseCommand

from predictions.services import (
    ensure_auto_monthly_prediction,
    next_month_target,
    run_monthly_rain_prediction,
)


class Command(BaseCommand):
    help = 'Auto-predict next month rainfall + cloudy chance (ML)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Run even if a prediction already exists for today',
        )

    def handle(self, *args, **options):
        target = next_month_target()
        self.stdout.write(
            f'Target month: {target["month_label"]} '
            f'(now {target["current_month_label"]})'
        )

        if options['force']:
            pred = run_monthly_rain_prediction(force_next_month_only=True, auto=True)
            self.stdout.write(self.style.SUCCESS(
                f'Forced auto-predict: {pred.month_label} {pred.rain_level} '
                f'~{pred.predicted_total_mm} mm · cloudy ~{pred.spring_dirt_probability_pct}%'
            ))
            return

        pred = ensure_auto_monthly_prediction()
        if pred is None:
            self.stdout.write(self.style.WARNING(
                'Skipped — already predicted today, or auto disabled / model not trained.'
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Auto-predicted: {pred.month_label} {pred.rain_level} '
            f'~{pred.predicted_total_mm} mm · cloudy ~{pred.spring_dirt_probability_pct}%'
        ))
