from django.urls import path

from .conversations import (
    ConversationDetailView,
    ConversationListView,
    ConversationTitleView,
)
from .views import chat_stream_view, chat_view

urlpatterns = [
    path('chat/', chat_view, name='chat'),
    path('chat/stream/', chat_stream_view, name='chat-stream'),
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<int:pk>/', ConversationDetailView.as_view(), name='conversation-detail'),
    path('conversations/<int:pk>/title/', ConversationTitleView.as_view(), name='conversation-title'),
]