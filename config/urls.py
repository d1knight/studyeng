from django.contrib import admin
from django.urls import path
from english import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.main_page, name='home'),
    path('courses/<int:course_id>/', views.course_detail),
    path('accounts/login/', views.reg, name='login'),
    path('api/v1/bot/generate-code/', views.generate_code, name='generate-code'),
    path("profile/", views.profile, name="profile"),
    path("logout/", views.logout_view, name="logout"),
    
]
