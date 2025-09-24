from django.contrib import admin
from django.urls import include, path
from english import views
from django.contrib.auth.views import LogoutView
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path("ckeditor/", include("ckeditor_uploader.urls")),
    path('', views.main_page, name='home'),
    path('courses/<int:course_id>/', views.course_detail, name='course_detail'),
    path('accounts/login/', views.reg, name='login'),
    path('api/v1/bot/generate-code/', views.generate_code, name='generate-code'),
    path("profile/", views.profile, name="profile"),
    path("logout/", views.logout_view, name="logout"),
    path("tariff/<int:tariff_id>/buy/", views.buy_tariff, name="buy_tariff"),
    path("topic/<int:topic_id>/", views.topic_detail, name="topic")
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)