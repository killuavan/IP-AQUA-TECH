"""Tests for monitoring models and views."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.management import call_command

from accounts.models import User
from .models import (
    MonitoringThreshold, StatusChoices, WarningLevel,
    WaterProduction, WaterQuality, WaterTank,
)


class WaterQualityModelTest(TestCase):
    def reading(self, **overrides):
        values = {
            'ph': Decimal('7.2'),
            'tds': Decimal('150'),
            'turbidity': Decimal('0.5'),
            'temperature': Decimal('25'),
            'flow_rate': Decimal('10'),
            'water_pressure': Decimal('2.5'),
            'water_level': Decimal('70'),
        }
        values.update(overrides)
        return WaterQuality(**values)

    def test_normal_classification(self):
        wq = WaterQuality(
            ph=Decimal('7.2'),
            tds=Decimal('150'),
            turbidity=Decimal('0.5'),
            temperature=Decimal('25'),
            flow_rate=Decimal('10'),
            water_pressure=Decimal('2.5'),
            water_level=Decimal('70'),
        )
        self.assertEqual(wq.classify_status(), StatusChoices.NORMAL)

    def test_critical_classification(self):
        wq = WaterQuality(
            ph=Decimal('4.0'),
            tds=Decimal('800'),
            turbidity=Decimal('10'),
            temperature=Decimal('45'),
            flow_rate=Decimal('1'),
            water_pressure=Decimal('0.3'),
            water_level=Decimal('20'),
        )
        self.assertEqual(wq.classify_status(), StatusChoices.CRITICAL)

    def test_save_sets_status(self):
        wq = WaterQuality.objects.create(
            ph=Decimal('7.0'),
            tds=Decimal('100'),
            turbidity=Decimal('0.3'),
            temperature=Decimal('24'),
            flow_rate=Decimal('12'),
            water_pressure=Decimal('3.0'),
            water_level=Decimal('80'),
        )
        self.assertEqual(wq.status, StatusChoices.NORMAL)

    def test_three_stage_warning_levels(self):
        self.assertEqual(
            self.reading(turbidity=Decimal('2')).classify_warning_level(),
            WarningLevel.FIRST,
        )
        self.assertEqual(
            self.reading(turbidity=Decimal('4')).classify_warning_level(),
            WarningLevel.MIDDLE,
        )
        self.assertEqual(
            self.reading(turbidity=Decimal('6')).classify_warning_level(),
            WarningLevel.DANGER,
        )

    def test_editable_threshold_changes_classification(self):
        MonitoringThreshold.objects.create(
            tds_normal_max=100,
            tds_danger_max=200,
        )
        self.assertEqual(
            self.reading(tds=Decimal('150')).classify_warning_level(),
            WarningLevel.FIRST,
        )

    def test_demo_readings_are_labeled_and_idempotent(self):
        options = {
            'start': date(2026, 9, 22),
            'end': date(2026, 9, 22),
            'interval_minutes': 10,
        }
        call_command('seed_demo_water_quality', **options)
        first_run_times = list(
            WaterQuality.objects.order_by('recorded_at').values_list('recorded_at', flat=True)
        )
        first_run_values = list(
            WaterQuality.objects.order_by('recorded_at').values_list(
                'ph', 'tds', 'turbidity', 'flow_rate', 'water_pressure', 'water_level',
            )
        )
        call_command('seed_demo_water_quality', **options)

        records = WaterQuality.objects.all()
        self.assertEqual(records.count(), 144)
        self.assertTrue(all('[SIMULATED DEMO' in row.notes for row in records))
        self.assertEqual(
            records.filter(recorded_at__date='2026-09-22').count(),
            144,
        )
        self.assertTrue(any(timestamp.second > 0 for timestamp in first_run_times))
        self.assertTrue(any(
            (later - earlier).total_seconds() != 600
            for earlier, later in zip(first_run_times, first_run_times[1:])
        ))
        self.assertEqual(
            list(WaterQuality.objects.order_by('recorded_at').values_list('recorded_at', flat=True)),
            first_run_times,
        )
        self.assertEqual(
            list(WaterQuality.objects.order_by('recorded_at').values_list(
                'ph', 'tds', 'turbidity', 'flow_rate', 'water_pressure', 'water_level',
            )),
            first_run_values,
        )
        max_changes = (Decimal('0.05'), Decimal('1.50'), Decimal('0.03'),
                       Decimal('0.30'), Decimal('0.05'), Decimal('0.30'))
        ordered_values = list(records.order_by('recorded_at').values_list(
            'ph', 'tds', 'turbidity', 'flow_rate', 'water_pressure', 'water_level',
        ))
        for previous, current in zip(ordered_values, ordered_values[1:]):
            for before, after, limit in zip(previous, current, max_changes):
                self.assertLessEqual(abs(after - before), limit)


class WaterTankModelTest(TestCase):
    def test_empty_status(self):
        tank = WaterTank.objects.create(
            name='Test Tank',
            capacity_liters=1000,
            current_level_percent=3,
        )
        self.assertEqual(tank.status, 'EMPTY')

    def test_volume_calculation(self):
        tank = WaterTank.objects.create(
            name='Calc Tank',
            capacity_liters=1000,
            current_level_percent=50,
        )
        self.assertEqual(float(tank.current_volume_liters), 500.0)


class MonitoringViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='monuser', password='pass12345', role=User.Role.OPERATOR,
        )
        self.client.login(username='monuser', password='pass12345')

    def test_water_quality_list(self):
        response = self.client.get(reverse('monitoring:water_quality_list'))
        self.assertEqual(response.status_code, 200)

    @patch('monitoring.views.timezone.now')
    def test_water_quality_list_hides_future_readings_without_demo_label(self, mock_now):
        current_time = timezone.make_aware(datetime(2026, 10, 4, 12, 0))
        mock_now.return_value = current_time
        reading_fields = {
            'ph': Decimal('7.2'),
            'tds': Decimal('150'),
            'turbidity': Decimal('0.5'),
            'temperature': Decimal('25'),
            'flow_rate': Decimal('10'),
            'water_pressure': Decimal('2.5'),
            'water_level': Decimal('70'),
            'notes': '[SIMULATED DEMO - NOT A POTABILITY TEST]',
        }
        available = WaterQuality.objects.create(
            recorded_at=current_time - timedelta(minutes=10), **reading_fields,
        )
        future = WaterQuality.objects.create(
            recorded_at=current_time + timedelta(days=1), **reading_fields,
        )

        response = self.client.get(reverse('monitoring:water_quality_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['page_obj'].object_list), [available])
        self.assertNotContains(response, 'SIMULATED')
        self.assertNotIn(future, response.context['page_obj'].object_list)

        detail_response = self.client.get(
            reverse('monitoring:water_quality_detail', args=[available.pk]),
        )
        self.assertNotContains(detail_response, 'SIMULATED')

    def test_create_water_quality(self):
        response = self.client.post(reverse('monitoring:water_quality_create'), {
            'ph': '7.1',
            'tds': '120',
            'turbidity': '0.4',
            'temperature': '26',
            'flow_rate': '15',
            'water_pressure': '2.8',
            'water_level': '75',
            'notes': 'Test reading',
            'recorded_at': timezone.now().strftime('%Y-%m-%dT%H:%M'),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(WaterQuality.objects.count(), 1)

    def test_production_list(self):
        WaterProduction.objects.create(
            date=timezone.now().date(),
            daily_production_liters=400,
            target_liters=500,
        )
        response = self.client.get(reverse('monitoring:production_list'))
        self.assertEqual(response.status_code, 200)

    @patch('iot.firebase_client.write_path')
    def test_operator_can_save_thresholds_and_sync_firebase(self, write_path):
        response = self.client.post(reverse('monitoring:threshold_settings'), {
            'ph_normal_min': '6.5',
            'ph_normal_max': '8.5',
            'ph_danger_min': '6.0',
            'ph_danger_max': '9.0',
            'tds_normal_max': '250',
            'tds_danger_max': '500',
            'turbidity_normal_max': '1',
            'turbidity_danger_max': '5',
            'battery_warning_percent': '30',
            'battery_critical_percent': '15',
            'battery_empty_voltage': '11.8',
            'battery_full_voltage': '12.7',
            'device_offline_seconds': '60',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MonitoringThreshold.objects.get().tds_normal_max, 250)
        write_path.assert_called_once()
