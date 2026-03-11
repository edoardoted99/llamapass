from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    invite_code = forms.CharField(
        max_length=20,
        required=False,
        help_text="Optional. If you have an invite code, your account will be approved instantly.",
    )

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]
