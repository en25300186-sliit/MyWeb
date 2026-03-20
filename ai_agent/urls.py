from django.urls import path

from . import views

urlpatterns = [
    path('ai/settings/', views.api_key_settings, name='ai_settings'),
    path('ai/chat/', views.chat_page, name='ai_chat'),
    path('ai/chat/new/', views.new_conversation, name='ai_chat_new'),
    path('ai/chat/send/', views.chat_send, name='ai_chat_send'),
    path('ai/neuro-symbolic/', views.neuro_symbolic_view, name='neuro_symbolic'),
    path('ai/neuro-symbolic/process/', views.neuro_symbolic_process, name='neuro_symbolic_process'),
]
