from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpRequest, JsonResponse
from .models import *
from django.core.cache import cache
from http import HTTPStatus
from .utils import generate_unique_otp
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
import random
from django.contrib import messages


def main_page(request):
    courses = Course.objects.all()
    tariffs = CourseTariff.objects.all()

    context = {
        'courses': courses,
        'tariffs': tariffs,
    }
    return render(request, 'english/index.html', context)

@login_required
def course_detail(request, course_id):
    try:
        course = get_object_or_404(Course, id=course_id)
        chapters = course.chapters.all().order_by('order_index').prefetch_related('topics')

        chapter_user_chapters = []
        if request.user.is_authenticated:
            for chapter in chapters:
                user_chapter, created = UserChapter.objects.get_or_create(user=request.user, chapter=chapter)
                if created or not hasattr(user_chapter, 'is_open'):
                    user_chapter.is_open = chapter.order_index == 1  # Открываем только первую главу
                    user_chapter.save()

                if chapter.order_index > 1:
                    prev_chapter = Chapter.objects.filter(course=course, order_index=chapter.order_index - 1).first()
                    if prev_chapter:
                        prev_user_chapter = request.user.user_chapters.filter(chapter=prev_chapter).first()
                        if prev_user_chapter and prev_user_chapter.completion_score is not None and prev_user_chapter.completion_score >= 80 and not user_chapter.is_open:
                            user_chapter.is_open = True
                            user_chapter.save()
                            user_chapter.refresh_from_db()

                chapter_user_chapters.append((chapter, user_chapter))

            # Проверяем доступность тем
            for chapter, user_chapter in chapter_user_chapters:
                topics = chapter.topics.all().order_by('order_index')
                for topic in topics:
                    topic.is_accessible = (user_chapter.is_open and 
                                          (topic.order_index == 1 or 
                                           request.user.payments.filter(tariff__course=course, status="paid").exists()))

            # Проверяем доступность контрольной работы
            for chapter, user_chapter in chapter_user_chapters:
                chapter.control_test_accessible = (chapter.order_index == 1 or 
                                                 (user_chapter.is_open and 
                                                  request.user.payments.filter(tariff__course=course, status="paid").exists()))

        context = {
            'course': course,
            'chapter_user_chapters': chapter_user_chapters,
            'chapters': chapters,
            'courses': Course.objects.all(),  # Для меню
        }
        return render(request, 'english/course.html', context)
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)

def topic_detail(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    exercises = Exercise.objects.filter(topic=topic).prefetch_related("questions")

    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        results = {}
        user_answers_dict = {}
        correct_answers_dict = {}

        for q in Question.objects.filter(exercise__topic=topic):
            blanks = {
                k.split('_')[-1]: v.strip()
                for k, v in request.POST.items()
                if k.startswith(f"q_{q.id}_blank")
            }

            if not any(blanks.values()):
                continue

            correct = q.correct_answer or {}
            correct_answers_dict[q.id] = correct

            is_correct = True
            for blank_key, correct_vals in correct.items():
                user_val = blanks.get(blank_key, "").strip().lower()
                if user_val:
                    if isinstance(correct_vals, list):
                        if user_val not in [a.strip().lower() for a in correct_vals]:
                            is_correct = False
                    else:
                        if user_val != str(correct_vals).strip().lower():
                            is_correct = False
                else:
                    is_correct = False

            UserQuestion.objects.update_or_create(
                user=request.user,
                question=q,
                defaults={"user_answer": blanks, "is_correct": is_correct}
            )
            user_answers_dict[q.id] = {"answer": blanks, "exercise_id": q.exercise.id}
            results[q.id] = is_correct

        return JsonResponse({
            "results": results,
            "user_answers": user_answers_dict,
            "correct_answers": correct_answers_dict,
        })

    return render(request, "english/topic.html", {
        "topic": topic,
        "exercises": exercises,
    })

def reg(request: HttpRequest):
    if request.method == 'POST':
        code = request.POST.get('code')

        session_data = cache.get(f'code_{code}')
        if not session_data:
            return render(request, 'english/reg.html', context={'error_message': 'Неверный код. Введите снова'})
        
        phone_number = session_data.get('phone_number')
        
        user, created = User.objects.get_or_create(phone_number=phone_number)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect('/')
    
    return render(request, 'english/reg.html')

@csrf_exempt
def generate_code(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=HTTPStatus.METHOD_NOT_ALLOWED)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=HTTPStatus.BAD_REQUEST)

    phone_number = data.get("phone_number")
    tg_id = data.get("tg_id")

    if not phone_number or not tg_id:
        return JsonResponse({"error": "phone_number and tg_id are required"}, status=HTTPStatus.BAD_REQUEST)

    user, created = User.objects.get_or_create(
        phone_number=phone_number, defaults={'tg_id': tg_id}
    )
    
    if created:
        user.set_unusable_password()
        user.save()
    elif user.tg_id != tg_id:
        user.tg_id = tg_id
        user.save()
    
    otp_code = generate_unique_otp()
    cache.set(f"code_{otp_code}", {'phone_number': phone_number}, timeout=60)

    return JsonResponse({"code": otp_code}, status=HTTPStatus.OK)

@login_required
def profile(request):
    user = request.user
    courses = Course.objects.filter(chapters__user_chapters__user=user).distinct()

    context = {
        'user': user,
        'courses': courses,  # Курсы пользователя, уже фильтруются
    }
    return render(request, "english/profile.html", context)

def logout_view(request):
    logout(request)
    return redirect('/')

@login_required
def buy_tariff(request, tariff_id):
    tariff = get_object_or_404(CourseTariff, id=tariff_id)

    if request.method == "POST":
        receipt = request.FILES.get("receipt")
        if not receipt:
            messages.error(request, "Пожалуйста, загрузите скриншот чека.")
            return render(request, "english/buy_tariff.html", {"tariff": tariff})

        Payment.objects.create(
            user=request.user,
            tariff=tariff,
            amount=tariff.price,
            receipt=receipt,
            status="pending"
        )
        messages.success(request, f"Платеж за тариф '{tariff.name}' отправлен на проверку. Проверьте статус в профиле.")
        return redirect("profile")

    return render(request, "english/buy_tariff.html", {"tariff": tariff})

def exercise_view(request, pk):
    exercise = Exercise.objects.get(pk=pk)
    questions = exercise.questions.all()

    for q in questions:
        q.rendered_text = q.render_with_inputs()

    return render(request, "exercise.html", {"exercise": exercise, "questions": questions})

@login_required
def control_test(request, chapter_id):
    chapter = get_object_or_404(Chapter, id=chapter_id)
    exercises = Exercise.objects.filter(topic__chapter=chapter).prefetch_related('questions')
    all_questions = Question.objects.filter(exercise__in=exercises).distinct()

    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        results = {}
        user_answers_dict = {}
        correct_answers_dict = {}

        selected_questions = request.session.get('control_questions', [])
        for q_id in selected_questions:
            q = get_object_or_404(Question, id=q_id)
            blanks = {
                k.split('_')[-1]: v.strip()
                for k, v in request.POST.items()
                if k.startswith(f"q_{q.id}_blank")
            }

            if not any(blanks.values()):
                continue

            correct = q.correct_answer or {}
            correct_answers_dict[q_id] = correct

            is_correct = True
            for blank_key, correct_vals in correct.items():
                user_val = blanks.get(blank_key, "").strip().lower()
                if user_val:
                    if isinstance(correct_vals, list):
                        if user_val not in [a.strip().lower() for a in correct_vals]:
                            is_correct = False
                    else:
                        if user_val != str(correct_vals).strip().lower():
                            is_correct = False
                else:
                    is_correct = False

            results[q_id] = is_correct
            user_answers_dict[q_id] = {"answer": blanks, "exercise_id": q.exercise.id}

        total_questions = len(selected_questions)
        correct_count = sum(1 for r in results.values() if r)
        score = (correct_count / total_questions * 100) if total_questions > 0 else 0

        user_chapter = request.user.user_chapters.filter(chapter=chapter).first()
        next_chapter_id = None
        if user_chapter:
            user_chapter.completion_score = score
            user_chapter.save()
            if score >= 80:
                user_chapter.is_open = True
                user_chapter.save()
                next_chapter = Chapter.objects.filter(course=chapter.course, order_index=chapter.order_index + 1).first()
                if next_chapter:
                    next_user_chapter, _ = UserChapter.objects.get_or_create(user=request.user, chapter=next_chapter)
                    next_user_chapter.is_open = True
                    next_user_chapter.save()
                    next_chapter_id = next_chapter.id

        return JsonResponse({
            "results": results,
            "user_answers": user_answers_dict,
            "correct_answers": correct_answers_dict,
            "score": score,
            "next_chapter_id": next_chapter_id,
        })

    selected_questions = random.sample(list(all_questions), min(20, all_questions.count()))
    request.session['control_questions'] = [q.id for q in selected_questions]

    for q in selected_questions:
        q.rendered_text = q.render_with_inputs()

    context = {
        "chapter": chapter,
        "questions": selected_questions,
        "course": chapter.course,
    }
    return render(request, "english/control_test.html", context)