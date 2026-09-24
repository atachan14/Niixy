import re
import unicodedata

from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.core.exceptions import ValidationError


User = get_user_model()
NIIXY_ID_PATTERN = re.compile(r'^[a-z0-9_]{3,20}$')


def is_emoji(character):
    codepoint = ord(character)
    return (
        0x1F000 <= codepoint <= 0x1FAFF
        or 0x2600 <= codepoint <= 0x27BF
        or codepoint in {0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139, 0x3030, 0x303D, 0x3297, 0x3299}
        or 0xFE00 <= codepoint <= 0xFE0F
        or codepoint == 0x20E3
    )


def display_width(value):
    return sum(
        0 if unicodedata.combining(character) else 2 if unicodedata.east_asian_width(character) in {'F', 'W'} else 1
        for character in value
    )


def clean_display_name_value(value):
    display_name = value.strip()
    if any(character in '\r\n' or unicodedata.category(character).startswith('C') for character in display_name):
        raise ValidationError('改行や制御文字は使えません。')
    if any(is_emoji(character) for character in display_name):
        raise ValidationError('絵文字は使えません。')
    if display_width(display_name) > 24:
        raise ValidationError('表示名は全角12文字、半角24文字相当までです。')
    return display_name


class SignUpForm(forms.Form):
    username = forms.CharField(min_length=3, max_length=20)
    display_name = forms.CharField(required=False, max_length=24)
    password = forms.CharField(min_length=8, widget=forms.PasswordInput)
    password_confirmation = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        if not NIIXY_ID_PATTERN.fullmatch(username):
            raise ValidationError('Niixy IDは英小文字、数字、_の3〜20文字で入力してください。')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('このNiixy IDはすでに使われています。')
        return username

    def clean_display_name(self):
        return clean_display_name_value(self.cleaned_data['display_name'])

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


class DisplayNameForm(forms.Form):
    display_name = forms.CharField(
        required=False,
        max_length=24,
        widget=forms.TextInput(attrs={'autocomplete': 'nickname'}),
    )

    def clean_display_name(self):
        return clean_display_name_value(self.cleaned_data['display_name'])
