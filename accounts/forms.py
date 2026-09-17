import re

from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.core.exceptions import ValidationError


User = get_user_model()
NIIXY_ID_PATTERN = re.compile(r'^[a-z0-9_]{3,20}$')


class SignUpForm(forms.Form):
    username = forms.CharField(min_length=3, max_length=20)
    password = forms.CharField(min_length=8, widget=forms.PasswordInput)
    password_confirmation = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        if not NIIXY_ID_PATTERN.fullmatch(username):
            raise ValidationError('Niixy IDは英小文字、数字、_の3〜20文字で入力してください。')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('このNiixy IDはすでに使われています。')
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirmation = cleaned_data.get('password_confirmation')

        if password and confirmation and password != confirmation:
            self.add_error('password_confirmation', 'Passwordが一致しません。')
        if password:
            try:
                password_validation.validate_password(password)
            except ValidationError as error:
                self.add_error('password', error)
        return cleaned_data


class LoginForm(forms.Form):
    username = forms.CharField(max_length=20)
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user = None

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username', '').lower()
        password = cleaned_data.get('password')
        if username and password:
            self.user = authenticate(self.request, username=username, password=password)
            if self.user is None:
                raise ValidationError('Niixy IDまたはPasswordが正しくありません。')
        return cleaned_data
