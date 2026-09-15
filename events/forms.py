from django import forms

from .models import Event


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title',
            'description',
            'capacity',
            'starts_at',
            'ends_at',
            'latitude',
            'longitude',
        ]
        widgets = {
            'starts_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'ends_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 5}),
        }

    def clean(self):
        cleaned_data = super().clean()
        starts_at = cleaned_data.get('starts_at')
        ends_at = cleaned_data.get('ends_at')

        if starts_at and ends_at and ends_at < starts_at:
            self.add_error('ends_at', '終了日時は開始日時以降にしてください。')

        return cleaned_data
