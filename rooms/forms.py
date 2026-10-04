from django import forms


class RoomCreateForm(forms.Form):
    name = forms.CharField(max_length=120)
    description = forms.CharField(required=False, max_length=10000, widget=forms.Textarea)
    latitude = forms.DecimalField(max_digits=9, decimal_places=6, min_value=-90, max_value=90)
    longitude = forms.DecimalField(max_digits=9, decimal_places=6, min_value=-180, max_value=180)


class RoomEditForm(forms.Form):
    name = forms.CharField(max_length=120)
    description = forms.CharField(required=False, max_length=10000, widget=forms.Textarea)
    latitude = forms.DecimalField(max_digits=9, decimal_places=6, min_value=-90, max_value=90)
    longitude = forms.DecimalField(max_digits=9, decimal_places=6, min_value=-180, max_value=180)


class BoardForm(forms.Form):
    name = forms.CharField(max_length=120)
    description = forms.CharField(required=False, max_length=10000, widget=forms.Textarea)


class BoardThreadCreateForm(forms.Form):
    title = forms.CharField(max_length=120)
    body = forms.CharField(widget=forms.Textarea, max_length=10000)
