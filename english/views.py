from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpRequest, JsonResponse
from .models import *
from django.core.cache import cache
from http import HTTPStatus
from .utils import generate_unique_otp
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth import login, logout
from .utils import render_question


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


def topic_detail(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    exercises = Exercise.objects.filter(topic=topic).prefetch_related("questions")

    user_answers = {}
    if request.method == "POST":
        for q in Question.objects.filter(exercise__topic=topic):
            user_answers[q.id] = request.POST.get(f"answer_{q.id}", "").strip()

    return render(request, "english/topic.html", {
        "topic": topic,
        "exercises": exercises,
        "user_answers": user_answers,
    })




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



@login_required
def buy_tariff(request, tariff_id):
    tariff = get_object_or_404(CourseTariff, id=tariff_id)

    if request.method == "POST":
        receipt = request.FILES.get("receipt")

        Payment.objects.create(
            user=request.user,
            tariff=tariff,
            amount=tariff.price,
            receipt=receipt,
            status="pending"
        )
        course = tariff.course
        chapters = course.chapters
        print(chapters)

        return redirect("profile")  # куда-то перенаправляем после отправки

    return render(request, "english/buy_tariff.html", {"tariff": tariff})


def exercise_view(request, pk):
    exercise = Exercise.objects.get(pk=pk)
    questions = exercise.questions.all()

    for q in questions:
        q.rendered_text = render_question(q.text)

    return render(request, "exercise.html", {"exercise": exercise, "questions": questions})