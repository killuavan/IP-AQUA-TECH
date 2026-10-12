"""Report generation tests."""
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from .utils import gather_report_data, generate_pdf, generate_excel


class ReportUtilsTest(TestCase):
    def test_gather_and_pdf(self):
        today = date.today()
        data = gather_report_data(today, today)
        pdf = generate_pdf(data, 'Test Report')
        self.assertTrue(len(pdf) > 100)
        self.assertTrue(pdf[:4] == b'%PDF')

    def test_excel_generation(self):
        today = date.today()
        data = gather_report_data(today, today)
        xlsx = generate_excel(data, 'Test Report')
        self.assertTrue(len(xlsx) > 100)


class ReportViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='repuser', password='pass12345', role=User.Role.ADMIN,
        )
        self.client.login(username='repuser', password='pass12345')

    def test_report_list(self):
        response = self.client.get(reverse('reports:report_list'))
        self.assertEqual(response.status_code, 200)

    def test_generate_page(self):
        response = self.client.get(reverse('reports:report_generate'))
        self.assertEqual(response.status_code, 200)
