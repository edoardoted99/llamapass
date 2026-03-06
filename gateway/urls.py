from django.urls import re_path

from gateway.views import proxy_ollama

urlpatterns = [
    re_path(r"^(?P<path>.+)$", proxy_ollama, name="ollama_proxy"),
]
