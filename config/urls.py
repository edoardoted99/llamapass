from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("dashboard/", include("accounts.dashboard_urls")),
    path("ollama/", include("gateway.urls")),
    path("", include("accounts.root_urls")),
]
