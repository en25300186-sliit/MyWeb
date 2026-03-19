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
            'preferred_model': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_preferred_model'}),
        }
        help_texts = {
            'preferred_model': 'Examples: openai/gpt-4o-mini (GitHub), gpt-4o (OpenAI), llama3-8b-8192 (Groq)',
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
