"""Dashboard tests."""
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from monitoring.models import WaterQuality


class DashboardTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='dashuser', password='pass12345', role=User.Role.OPERATOR,
        )

    def test_dashboard_loads(self):
        self.client.login(username='dashuser', password='pass12345')
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'System overview')
        self.assertContains(response, 'Sensor readings')
        self.assertContains(response, 'pH Level')
        self.assertContains(response, 'TDS')
        self.assertContains(response, 'Turbidity')
        self.assertContains(response, 'Battery')

    def test_chart_data_api(self):
        self.client.login(username='dashuser', password='pass12345')
        response = self.client.get(reverse('dashboard:chart_data'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('production', data)
        self.assertIn('solar', data)
        self.assertIn('battery', data)
        self.assertIn('water_quality', data)

    def test_chart_data_api_filters_water_quality_by_selected_datetime(self):
        self.client.login(username='dashuser', password='pass12345')
        start = timezone.make_aware(datetime(2026, 10, 4, 10, 0))
        inside = WaterQuality.objects.create(
            ph=Decimal('7.2'), tds=Decimal('150'), turbidity=Decimal('0.5'),
            temperature=Decimal('25'), flow_rate=Decimal('10'),
            water_pressure=Decimal('2.5'), water_level=Decimal('70'),
            recorded_at=start + timedelta(minutes=10),
        )
        WaterQuality.objects.create(
            ph=Decimal('7.3'), tds=Decimal('151'), turbidity=Decimal('0.6'),
            temperature=Decimal('25'), flow_rate=Decimal('10'),
            water_pressure=Decimal('2.5'), water_level=Decimal('70'),
            recorded_at=start + timedelta(hours=2),
        )
        url = reverse('dashboard:chart_data')

        with patch('dashboard.views.timezone.now', return_value=start + timedelta(hours=1)):
            response = self.client.get(url, {
                'from_datetime': (start).strftime('%Y-%m-%dT%H:%M'),
                'to_datetime': (start + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
            })

        self.assertEqual(response.status_code, 200)
        data = response.json()['water_quality']
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['records'][0]['ph'], float(inside.ph))

    def test_dashboard_shows_latest_due_reading_not_future_reading(self):
        self.client.login(username='dashuser', password='pass12345')
        now = timezone.make_aware(datetime(2026, 10, 4, 12, 0))
        reading_values = {
            'ph': Decimal('7.1'),
            'tds': Decimal('120'),
            'turbidity': Decimal('0.4'),
            'temperature': Decimal('25'),
            'flow_rate': Decimal('10'),
            'water_pressure': Decimal('2.5'),
            'water_level': Decimal('70'),
        }
        due_reading = WaterQuality.objects.create(
            recorded_at=now - timedelta(minutes=10), **reading_values,
        )
        WaterQuality.objects.create(
            recorded_at=now + timedelta(days=1),
            ph=Decimal('8.1'),
            **{key: value for key, value in reading_values.items() if key != 'ph'},
        )

        with (
            patch('dashboard.views.timezone.now', return_value=now),
            patch('iot.services.mark_stale_devices_offline'),
            patch('iot.services.pull_latest_from_firebase', return_value={'readings': {}}),
            patch('predictions.weather_client.fetch_weather', return_value=None),
        ):
            response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['latest_wq'], due_reading)
        self.assertEqual(response.context['selected_wq'], due_reading)
        self.assertContains(response, '7.10')

        chart_response = self.client.get(reverse('dashboard:chart_data'))
        self.assertEqual(chart_response.status_code, 200)
        self.assertEqual(
            len(chart_response.json()['water_quality']['labels']),
            1,
        )
