"""Role-based access decorators."""
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def admin_required(view_func):
    """Allow only Admin users (or superusers)."""
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not (request.user.is_admin_user or request.user.is_superuser):
            raise PermissionDenied('Admin access required.')
        return view_func(request, *args, **kwargs)
    return _wrapped
