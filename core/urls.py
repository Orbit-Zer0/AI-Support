from django.contrib import admin
from django.urls import path, include
from apps.chat.pages import IndexView

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('admin/', admin.site.urls),
    path('api/', include('apps.chat.urls')),
    path('api/', include('apps.accounts.urls')),
    path('api/', include('apps.crisis.urls')),
]