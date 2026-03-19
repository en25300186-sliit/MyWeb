import uuid

from django.contrib.auth.models import User
from django.db import models

# ---------------------------------------------------------------------------
# Provider catalogue – single source of truth for base URLs and default models
# ---------------------------------------------------------------------------
PROVIDER_CONFIG = {
    'github': {
        'base_url': 'https://models.inference.ai.azure.com',
        'default_model': 'openai/gpt-4o-mini',
        'label': 'GitHub Models (Default)',
        'models': [
            'openai/gpt-4o-mini',
            'openai/gpt-4o',
            'meta/llama-3.1-8b-instruct',
            'meta/llama-3.1-70b-instruct',
            'meta/llama-3.3-70b-instruct',
            'microsoft/phi-4',
            'mistral-ai/mistral-small',
            'cohere/cohere-command-r',
        ],
    },
    'openai': {
        'base_url': 'https://api.openai.com/v1',
        'default_model': 'gpt-4o-mini',
        'label': 'OpenAI',
        'models': [
            'gpt-4o-mini',
            'gpt-4o',
            'gpt-4-turbo',
            'gpt-3.5-turbo',
        ],
    },
    'groq': {
        'base_url': 'https://api.groq.com/openai/v1',
        'default_model': 'llama3-8b-8192',
        'label': 'Groq',
        'models': [
            'llama3-8b-8192',
            'llama3-70b-8192',
            'mixtral-8x7b-32768',
            'gemma-7b-it',
        ],
    },
}


class UserAPIKey(models.Model):
    """Stores one encrypted API key and provider preference per user."""

    PROVIDER_CHOICES = [
        ('github', 'GitHub Models (Default)'),
        ('openai', 'OpenAI'),
        ('groq', 'Groq'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='api_key_config')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='github')
    encrypted_api_key = models.TextField(help_text='Fernet-encrypted API key')
    preferred_model = models.CharField(max_length=100, default='openai/gpt-4o-mini')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User API Key'
        verbose_name_plural = 'User API Keys'

    def __str__(self):
        return f'{self.user.username} – {self.provider}'

    def get_base_url(self) -> str:
        cfg = PROVIDER_CONFIG.get(self.provider, PROVIDER_CONFIG['github'])
        return cfg['base_url']

    def get_decrypted_api_key(self) -> str:
        from .encryption import decrypt_value
        return decrypt_value(self.encrypted_api_key)


class AgentConversation(models.Model):
    """Groups a series of messages into a single chat session."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_conversations')
    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.user.username} – {self.session_id}'


class AgentMessage(models.Model):
    """A single turn (user / assistant / tool result) inside a conversation."""

    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('tool', 'Tool'),
    ]

    conversation = models.ForeignKey(
        AgentConversation, on_delete=models.CASCADE, related_name='messages'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    tool_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.role}] {self.content[:60]}'
