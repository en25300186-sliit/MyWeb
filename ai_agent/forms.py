from django import forms

from .models import PROVIDER_CONFIG, UserAPIKey


class APIKeySettingsForm(forms.ModelForm):
    """Form for configuring a user's AI provider, API key, and preferred model."""

    api_key = forms.CharField(
        widget=forms.PasswordInput(render_value=False, attrs={'class': 'form-control', 'placeholder': 'Paste your API key / Personal Access Token'}),
        label='API Key / Personal Access Token',
        help_text='Your key is encrypted before storage and never shown again.',
        required=True,
    )

    class Meta:
        model = UserAPIKey
        fields = ['provider', 'preferred_model']
        widgets = {
            'provider': forms.Select(attrs={'class': 'form-select', 'id': 'id_provider'}),
            'preferred_model': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_preferred_model',
                'list': 'model-suggestions',
            }),
        }
        help_texts = {
            'preferred_model': (
                'Select a suggested model from the list or type a custom model name. '
                'GitHub: openai/gpt-4o-mini · OpenAI: gpt-4o-mini · Groq: llama3-8b-8192'
            ),
        }

    def __init__(self, *args, **kwargs):
        # Pass the current UserAPIKey instance so we can pre-fill the provider
        super().__init__(*args, **kwargs)
        # Build dynamic provider choices with default model hints
        choices = []
        for value, label in UserAPIKey.PROVIDER_CHOICES:
            cfg = PROVIDER_CONFIG.get(value, {})
            hint = cfg.get('default_model', '')
            choices.append((value, f'{label}  (default model: {hint})'))
        self.fields['provider'].choices = choices

    def clean(self):
        cleaned_data = super().clean()
        provider = cleaned_data.get('provider')
        model = cleaned_data.get('preferred_model', '').strip()

        if provider and model:
            cfg = PROVIDER_CONFIG.get(provider, {})
            known_models = cfg.get('models', [])
            if known_models and model not in known_models:
                self.add_error(
                    'preferred_model',
                    f'"{model}" is not a recognised model for {cfg.get("label", provider)}. '
                    f'Please choose one of the known models: {", ".join(known_models)}.',
                )

        return cleaned_data
