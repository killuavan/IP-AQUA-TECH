"""Filter app tests."""
from decimal import Decimal
from django.test import TestCase
from .models import Filter, FilterCondition


class FilterModelTest(TestCase):
    def test_needs_replacement(self):
        f = Filter.objects.create(
            name='Worn Filter',
            filter_type='SEDIMENT',
            life_percentage=Decimal('8'),
        )
        self.assertTrue(f.needs_replacement)
        self.assertEqual(f.condition, FilterCondition.REPLACE)

    def test_good_condition(self):
        f = Filter.objects.create(
            name='New Filter',
            filter_type='CARBON',
            life_percentage=Decimal('90'),
        )
        self.assertEqual(f.condition, FilterCondition.EXCELLENT)
        self.assertFalse(f.needs_replacement)
