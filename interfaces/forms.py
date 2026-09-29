from django import forms
from django.forms import BaseFormSet, formset_factory

from .models import FieldDefinition, FieldType


class InterfaceDraftForm(forms.Form):
    name = forms.CharField(label='Interface名', max_length=120, widget=forms.TextInput(attrs={'placeholder': '名前'}))
    description = forms.CharField(
        label='詳細',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': '詳細'}),
    )
class InterfaceDraftFieldForm(forms.Form):
    field_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    definition_id = forms.IntegerField(widget=forms.HiddenInput)
    required = forms.BooleanField(label='必須', required=False)
    DELETE = forms.BooleanField(label='削除', required=False)


class BaseInterfaceDraftFieldFormSet(BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        definition_ids = [
            form.cleaned_data['definition_id']
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE')
        ]
        if len(definition_ids) != len(set(definition_ids)):
            raise forms.ValidationError('同じFieldを重複して追加できません。')


InterfaceDraftFieldFormSet = formset_factory(
    InterfaceDraftFieldForm,
    formset=BaseInterfaceDraftFieldFormSet,
    extra=0,
)


class FieldDefinitionForm(forms.Form):
    name = forms.CharField(label='Field名', max_length=120, widget=forms.TextInput(attrs={'placeholder': '名前'}))
    description = forms.CharField(
        label='詳細',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': '詳細'}),
    )
    field_type = forms.ChoiceField(label='型', choices=FieldType.choices)
    options = forms.CharField(
        label='選択肢',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': '選択肢（1行に1つ）'}),
    )
    synonym_targets = forms.ModelMultipleChoiceField(
        label='片同義',
        required=False,
        queryset=FieldDefinition.objects.none(),
        widget=forms.MultipleHiddenInput,
    )

    def __init__(self, *args, definition=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = FieldDefinition.objects.filter(
            status=FieldDefinition.ACTIVE,
            current_version__isnull=False,
        ).select_related('creator', 'current_version')
        if definition:
            queryset = queryset.exclude(pk=definition.pk)
        self.fields['synonym_targets'].queryset = queryset.order_by('creator__username', 'name')

    def clean(self):
        cleaned_data = super().clean()
        field_type = cleaned_data.get('field_type')
        options = [line.strip() for line in cleaned_data.get('options', '').splitlines() if line.strip()]
        if field_type in {FieldType.SINGLE_CHOICE, FieldType.MULTIPLE_CHOICE}:
            if not options:
                self.add_error('options', '選択型には一つ以上の選択肢が必要です。')
            elif len(options) != len(set(options)):
                self.add_error('options', '同じ選択肢を重複して指定できません。')
        cleaned_data['settings'] = {'options': options} if options else {}
        return cleaned_data
