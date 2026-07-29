from django.contrib import admin
from django.urls import path
from core.views import dashboard_view, login_view, logout_view
from api.api import api

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),
    path('login/', login_view, name='login'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('logout/', logout_view, name='logout'),
    path('', login_view),
]