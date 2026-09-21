from django import forms


class ThreadCreateForm(forms.Form):
    title = forms.CharField(max_length=120)
    body = forms.CharField(widget=forms.Textarea, max_length=10000)
    latitude = forms.DecimalField(max_digits=9, decimal_places=6, min_value=-90, max_value=90)
    longitude = forms.DecimalField(max_digits=9, decimal_places=6, min_value=-180, max_value=180)


class ThreadPostForm(forms.Form):
    body = forms.CharField(widget=forms.Textarea, max_length=10000)
