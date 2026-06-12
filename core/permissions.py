from functools import wraps

from django.shortcuts import redirect
from django.contrib import messages

from .models import Profile, AuditLog


def get_user_role(user):
    if not user.is_authenticated:
        return None

    try:
        return user.profile.role
    except Profile.DoesNotExist:
        return None


def role_required(allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            role = get_user_role(request.user)

            if role not in allowed_roles:
                username = request.user.username if request.user.is_authenticated else "Anonymous"

                AuditLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    action_type="SECURITY",
                    description=(
                        f"BLOCKED unauthorized action. "
                        f"User: {username}. "
                        f"Role: {role}. "
                        f"Attempted view: {view_func.__name__}. "
                        f"Allowed roles: {allowed_roles}. "
                        f"Reason: role not permitted."
                    )
                )

                messages.error(
                    request,
                    "Access denied. You do not have permission."
                )

                return redirect("dashboard")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator