"""Solar app tests."""
from decimal import Decimal
from django.test import TestCase
from .models import SolarSystem, Battery, PowerStatus, ChargingStatus


class SolarSystemTest(TestCase):
    def test_power_calculation_and_status(self):
        s = SolarSystem.objects.create(
            panel_voltage=Decimal('24.0'),
            panel_current=Decimal('10.0'),
            power_output=Decimal('0'),
            power_consumption=Decimal('100'),
        )
        self.assertEqual(float(s.power_output), 240.0)
        self.assertEqual(s.status, PowerStatus.NORMAL)

    def test_offline_status(self):
        s = SolarSystem.objects.create(
            panel_voltage=Decimal('0'),
            panel_current=Decimal('0'),
            power_output=Decimal('0'),
        )
        self.assertEqual(s.status, PowerStatus.OFFLINE)


class BatteryTest(TestCase):
    def test_critical_battery(self):
        b = Battery.objects.create(
            name='Low Batt',
            voltage=Decimal('20'),
            percentage=Decimal('10'),
            charging_status=ChargingStatus.DISCHARGING,
        )
        self.assertEqual(b.status, PowerStatus.CRITICAL)
