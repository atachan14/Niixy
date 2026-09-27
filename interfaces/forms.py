from django import forms
from django.forms import BaseFormSet, formset_factory

from .models import FieldType, Interface


class InterfaceDraftForm(forms.Form):
    name = forms.CharField(label='Interface名', max_length=120, widget=forms.TextInput(attrs={'placeholder': '名前'}))
    description = forms.CharField(
        label='詳細',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': '詳細'}),
    )
    required_interfaces = forms.ModelMultipleChoiceField(
        label='Require',
        required=False,
        queryset=Interface.objects.none(),
        widget=forms.MultipleHiddenInput,
    )

    def __init__(self, *args, user=None, draft=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Interface.objects.filter(
            status=Interface.ACTIVE,
            current_version__isnull=False,
        ).select_related('creator', 'current_version')
        if draft and draft.interface_id:
            queryset = queryset.exclude(pk=draft.interface_id)
        self.fields['required_interfaces'].queryset = queryset.order_by('creator__username', 'name')


class InterfaceDraftFieldForm(forms.Form):
    field_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    label = forms.CharField(label='Field名', max_length=120, widget=forms.TextInput(attrs={'placeholder': '名前'}))
    field_type = forms.ChoiceField(label='型', choices=FieldType.choices)
    required = forms.BooleanField(label='必須', required=False)
    options = forms.CharField(
        label='選択肢',
        required=False,
        widget=forms.Textarea(attrs={'rows': 1, 'placeholder': '選択肢（1行に1つ）'}),
    )
    DELETE = forms.BooleanField(label='削除', required=False)

    def clean(self):
        cleaned_data = super().clean()
        field_type = cleaned_data.get('field_type')
        options = [line.strip() for line in cleaned_data.get('options', '').splitlines() if line.strip()]
        if field_type in {FieldType.SINGLE_CHOICE, FieldType.MULTIPLE_CHOICE}:
            if not options:
                self.add_error('options', '選択型には一つ以上の選択肢が必要です。')
            elif len(options) != len(set(options)):
                self.add_error('options', '同じ選択肢を重複して指定できません。')
        cleaned_data['normalized_options'] = options
        return cleaned_data


class BaseInterfaceDraftFieldFormSet(BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        labels = [
            form.cleaned_data['label'].strip().casefold()
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE')
        ]
        if len(labels) != len(set(labels)):
            raise forms.ValidationError('同じField名を重複して指定できません。')


InterfaceDraftFieldFormSet = formset_factory(
    InterfaceDraftFieldForm,
    formset=BaseInterfaceDraftFieldFormSet,
    extra=0,
)
