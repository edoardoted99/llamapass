from django.urls import path

from accounts import views as account_views
from keys import views as key_views

urlpatterns = [
    path("", account_views.dashboard, name="dashboard"),
    path("keys/", key_views.key_list, name="key_list"),
    path("keys/create/", key_views.key_create, name="key_create"),
    path("keys/<int:pk>/revoke/", key_views.key_revoke, name="key_revoke"),
    path("test/", account_views.test_api, name="test_api"),
    path("usage/", account_views.usage_guide, name="usage"),
]
