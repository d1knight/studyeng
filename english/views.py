from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpRequest, JsonResponse
from .models import *
from django.core.cache import cache
from http import HTTPStatus
from .utils import generate_unique_otp
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth import login, logout



def main_page(request):
    courses = Course.objects.all()
    tariffs = CourseTariff.objects.all()
    print(tariffs)

    context = {
        'courses': courses,
        'tariffs': tariffs,
    
    }
    return render(request, 'english/index.html', context)


def course_detail(request, course_id):
    course = Course.objects.filter(id=course_id).first()
    courses = Course.objects.all()

    context = {
        'course': course,
        'courses': courses
    }
    return render(request, 'english/course.html', context)


def reg(request: HttpRequest):
    if request.method == 'POST':
        print('Reg post')
        code = request.POST.get('code')

        session_data = cache.get(f'code_{code}')
        if not session_data:
            return render(request, 'english/reg.html', context={'error_message': 'Неверный код. Введите снова'})
        

        phone_number = session_data.get('phone_number')
        
        user, created = User.objects.get_or_create(phone_number=phone_number)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect('/')
    
    return render(request, 'english/reg.html')


@csrf_exempt  # отключаем CSRF для этого API
def generate_code(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=HTTPStatus.METHOD_NOT_ALLOWED)

    try:
        data = json.loads(request.body)  # получаем JSON
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=HTTPStatus.BAD_REQUEST)

    phone_number = data.get("phone_number")
    tg_id = data.get("tg_id")

    if not phone_number or not tg_id:
        return JsonResponse({"error": "phone_number and tg_id are required"}, status=HTTPStatus.BAD_REQUEST)

    # Создаем или обновляем пользователя
    user, created = User.objects.get_or_create(
        phone_number=phone_number, defaults={'tg_id': tg_id}
    )
    
    if created:
        user.set_unusable_password()
        user.save()
    elif user.tg_id != tg_id:
        user.tg_id = tg_id
        user.save()
    
    # Генерируем OTP и сохраняем в кэш
    otp_code = generate_unique_otp()
    cache.set(f"code_{otp_code}", {'phone_number': phone_number}, timeout=60) 

    return JsonResponse({"code": otp_code}, status=HTTPStatus.OK)


from django.contrib.auth.decorators import login_required

@login_required
def profile(request):
    user = request.user
    courses = Course.objects.filter(chapters__user_chapters__user=user).distinct()

    return render(request, "english/profile.html", {
        "user": user,
        "courses": courses,
    })


def logout_view(request):
    logout(request)
    return redirect('/')