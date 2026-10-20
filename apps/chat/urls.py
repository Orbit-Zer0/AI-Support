from django.urls import path

from .conversations import ConversationDetailView, ConversationListView
from .views import chat_view

urlpatterns = [
    path('chat/', chat_view, name='chat'),
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<int:pk>/', ConversationDetailView.as_view(), name='conversation-detail'),
]