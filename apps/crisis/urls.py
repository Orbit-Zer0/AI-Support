from django.urls import path

from .views import CrisisContactsView

urlpatterns = [
    path('crisis-contacts/', CrisisContactsView.as_view(), name='crisis-contacts'),
]