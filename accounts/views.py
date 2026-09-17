from django.contrib.auth import login, logout
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .forms import LoginForm, SignUpForm


def form_errors(form):
    return {field_name: list(errors) for field_name, errors in form.errors.items()}


@require_POST
def signup(request):
    form = SignUpForm(request.POST)
    if form.is_valid():
        try:
            user = get_user_model().objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
        except IntegrityError:
            form.add_error('username', 'このNiixy IDはすでに使われています。')
        else:
            login(request, user)
            return JsonResponse({'username': user.username})

    return JsonResponse({'errors': form_errors(form)}, status=400)


@require_POST
def login_view(request):
    form = LoginForm(request, request.POST)
    if form.is_valid():
        login(request, form.user)
        return JsonResponse({'username': form.user.username})
    return JsonResponse({'errors': form_errors(form)}, status=400)


@require_POST
def logout_view(request):
    logout(request)
    return redirect('events:map')
