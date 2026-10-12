"""Authentication and user management views."""
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.middleware.csrf import rotate_token
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .decorators import admin_required
from .forms import (
    CustomPasswordChangeForm,
    LoginForm,
    ProfileUpdateForm,
    RegistrationForm,
    UserCreateForm,
    UserUpdateForm,
)
from .models import User


@never_cache
@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                messages.error(request, 'This account is deactivated.')
                return render(request, 'accounts/login.html', {'form': form})
            login(request, user)
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            next_url = request.GET.get('next') or 'dashboard:index'
            return redirect(next_url)
        messages.error(request, 'Invalid username or password.')
    return render(request, 'accounts/login.html', {'form': form})


@never_cache
@require_http_methods(['GET', 'POST'])
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Registration successful. You can now sign in.')
        return redirect('accounts:login')
    return render(request, 'accounts/register.html', {'form': form})


def csrf_failure(request, reason=''):
    """Refresh stale browser CSRF state and send the user back to login."""
    rotate_token(request)
    messages.error(request, 'Your form expired. Please try again from the refreshed login page.')
    return redirect('accounts:login')


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('accounts:login')


@login_required
@require_http_methods(['GET', 'POST'])
def change_password(request):
    form = CustomPasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Password changed successfully.')
        return redirect('dashboard:index')
    return render(request, 'accounts/change_password.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
def profile(request):
    form = ProfileUpdateForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('accounts:profile')
    return render(request, 'accounts/profile.html', {'form': form})


@admin_required
def user_list(request):
    q = request.GET.get('q', '').strip()
    role = request.GET.get('role', '')
    users = User.objects.all()
    if q:
        users = users.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )
    if role:
        users = users.filter(role=role)
    paginator = Paginator(users, 10)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/user_list.html', {
        'page_obj': page,
        'q': q,
        'role': role,
    })


@admin_required
@require_http_methods(['GET', 'POST'])
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'User created successfully.')
        return redirect('accounts:user_list')
    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'Add User',
    })


@admin_required
@require_http_methods(['GET', 'POST'])
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserUpdateForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'User updated successfully.')
        return redirect('accounts:user_list')
    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'Edit User',
        'user_obj': user,
    })


@admin_required
@require_http_methods(['POST'])
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('accounts:user_list')
    username = user.username
    user.delete()
    messages.success(request, f'User "{username}" deleted.')
    return redirect('accounts:user_list')


@admin_required
@require_http_methods(['POST'])
def user_toggle_active(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('accounts:user_list')
    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    state = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User "{user.username}" {state}.')
    return redirect('accounts:user_list')
