from django.contrib import admin

from .models import AgentConversation, AgentMessage, UserAPIKey


@admin.register(UserAPIKey)
class UserAPIKeyAdmin(admin.ModelAdmin):
    list_display = ['user', 'provider', 'preferred_model', 'updated_at']
    list_filter = ['provider']
    search_fields = ['user__username']
    readonly_fields = ['encrypted_api_key', 'created_at', 'updated_at']


@admin.register(AgentConversation)
class AgentConversationAdmin(admin.ModelAdmin):
    list_display = ['user', 'session_id', 'created_at', 'updated_at']
    list_filter = ['user']
    readonly_fields = ['session_id', 'created_at', 'updated_at']


@admin.register(AgentMessage)
class AgentMessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'role', 'tool_name', 'created_at']
    list_filter = ['role']
    search_fields = ['content']
    readonly_fields = ['created_at']
