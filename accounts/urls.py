from django.contrib.auth import views as auth_views
from django.urls import path

from . import views as account_views

urlpatterns = [
    path("login/", account_views.custom_login, name="login"),
    path("logout/", auth_views.LogoutView.as_view(http_method_names=["get", "post", "options"]), name="logout"),
    path("register/", account_views.register, name="register"),
    path("pending/", account_views.pending, name="pending"),
    path(
        "password/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change.html",
            success_url="/accounts/password/done/",
        ),
        name="password_change",
    ),
    path(
        "password/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html",
        ),
        name="password_change_done",
    ),
]
