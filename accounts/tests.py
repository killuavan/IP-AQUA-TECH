"""Tests for accounts app."""
from django.test import TestCase, Client
from django.urls import reverse
from .models import User


class UserModelTest(TestCase):
    def test_create_admin_user(self):
        user = User.objects.create_user(
            username='testadmin',
            password='testpass123',
            role=User.Role.ADMIN,
        )
        self.assertTrue(user.is_admin_user)
        self.assertFalse(user.is_operator)

    def test_create_operator_user(self):
        user = User.objects.create_user(
            username='testop',
            password='testpass123',
            role=User.Role.OPERATOR,
        )
        self.assertTrue(user.is_operator)
        self.assertFalse(user.is_admin_user)


class AuthenticationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='loginuser',
            password='securepass1',
            role=User.Role.OPERATOR,
        )

    def test_login_success(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'loginuser',
            'password': 'securepass1',
        })
        self.assertEqual(response.status_code, 302)

    def test_login_failure(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'loginuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response.url)

    def test_user_list_admin_only(self):
        self.client.login(username='loginuser', password='securepass1')
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 403)

        admin = User.objects.create_user(
            username='admin2', password='adminpass1', role=User.Role.ADMIN,
        )
        self.client.login(username='admin2', password='adminpass1')
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 200)
