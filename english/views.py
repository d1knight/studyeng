from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpRequest, JsonResponse
from .forms import CommentForm
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
from types import SimpleNamespace


def main_page(request):
    courses = Course.objects.all()
    tariffs = CourseTariff.objects.all()
    comment_form = CommentForm()

    if request.method == "POST":
        if not request.user.is_authenticated:
            messages.error(request, "Войдите, чтобы оставить комментарий.")
        else:
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.user = request.user
                comment.save()
                messages.success(request, "Комментарий добавлен!")
                comment_form = CommentForm()  # очистка формы

    comments = Comment.objects.all().order_by('-created_at')

    context = {
        'courses': courses,
        'tariffs': tariffs,
        'comments': comments,
        'comment_form': comment_form,
    }
    return render(request, 'english/index.html', context)


def course_detail(request, course_id):
    try:
        course = get_object_or_404(Course, id=course_id)
        chapters = course.chapters.all().order_by('order_index').prefetch_related('topics')

        chapter_user_chapters = []
        user = request.user if request.user.is_authenticated else None

        # проверяем, есть ли у залогиненного пользователя оплаченный тариф для этого курса
        has_paid_access = False
        if user:
            has_paid_access = user.payments.filter(tariff__course=course, status="paid").exists()

        for chapter in chapters:
            if user:
                user_chapter, created = UserChapter.objects.get_or_create(user=user, chapter=chapter)
                # по умолчанию открыта только первая глава
                if created or not hasattr(user_chapter, 'is_open'):
                    user_chapter.is_open = chapter.order_index == 1
                    user_chapter.save()

                # если предыдущая глава пройдена >= 80 — открыть текущую
                if chapter.order_index > 1:
                    prev_chapter = Chapter.objects.filter(course=course, order_index=chapter.order_index - 1).first()
                    if prev_chapter:
                        prev_user_chapter = user.user_chapters.filter(chapter=prev_chapter).first()
                        if prev_user_chapter and prev_user_chapter.completion_score is not None and prev_user_chapter.completion_score >= 80 and not user_chapter.is_open:
                            user_chapter.is_open = True
                            user_chapter.save()
                curr_user_chapter = user_chapter
            else:
                # для анонима не создаём записи в БД — но в шаблоне нам удобнее иметь объект с нужными атрибутами
                curr_user_chapter = SimpleNamespace(is_open=False, completion_score=None)

            # Проверяем доступность тем в главе
            topics = chapter.topics.all().order_by('order_index')
            for topic in topics:
                # публичные темы всегда доступны
                if topic.is_public:
                    topic.is_accessible = True
                else:
                    # непубличные: доступны только если глава открыта и пользователь авторизован + (первая тема или оплачен тариф)
                    topic.is_accessible = bool(
                        curr_user_chapter.is_open and
                        user and
                        (topic.order_index == 1 or has_paid_access)
                    )

            # Контрольная работа доступна только если глава открыта и тариф оплачен
            chapter.control_test_accessible = bool(curr_user_chapter.is_open and user and has_paid_access)

            chapter_user_chapters.append((chapter, curr_user_chapter))

        context = {
            'course': course,
            'chapter_user_chapters': chapter_user_chapters,
            'chapters': chapters,
            'courses': Course.objects.all(),  # Для меню
            'user_has_tariff': has_paid_access,  # <-- флаг для шаблона
        }
        return render(request, 'english/course.html', context)
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)
    

def topic_detail(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    user = request.user if request.user.is_authenticated else None

    # Проверка доступа: публичная — всегда, иначе — только если пользователь авторизован,
    # глава открыта и (первая тема или оплачен тариф)
    allowed = topic.is_public
    if not allowed and user:
        user_chapter = user.user_chapters.filter(chapter=topic.chapter).first()
        has_paid = user.payments.filter(tariff__course=topic.chapter.course, status="paid").exists()
        if user_chapter and user_chapter.is_open and (topic.order_index == 1 or has_paid):
            allowed = True

    if not allowed:
        # можно перенаправить на страницу курса с сообщением
        messages.info(request, "Тема недоступна. Авторизуйтесь и/или купите тариф для доступа.")
        return redirect('course_detail', course_id=topic.chapter.course.id)

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

            # Сохраняем ответ только если пользователь авторизован
            if request.user.is_authenticated:
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

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Comment
from .forms import CommentForm

@login_required
def profile(request):
    comments = Comment.objects.all().order_by('-created_at')

    # --- Добавление комментария ---
    if request.method == "POST" and not request.headers.get("x-requested-with") == "XMLHttpRequest":
        if "add_comment" in request.POST:
            form = CommentForm(request.POST)
            if form.is_valid():
                new_comment = form.save(commit=False)
                new_comment.user = request.user
                new_comment.save()
                return redirect('profile')  # обычная форма добавления
        else:
            form = CommentForm()
    else:
        form = CommentForm()

    # --- AJAX: редактирование комментария ---
    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        # Редактирование
        if "edit_comment" in request.POST:
            comment_id = request.POST.get("comment_id")
            new_text = request.POST.get("text")
            comment = get_object_or_404(Comment, id=comment_id, user=request.user)
            comment.text = new_text
            comment.save()
            return JsonResponse({
                "success": True,
                "comment": {
                    "id": comment.id,
                    "text": comment.text
                }
            })

        # Удаление
        elif "delete_comment" in request.POST:
            comment_id = request.POST.get("comment_id")
            comment = get_object_or_404(Comment, id=comment_id, user=request.user)
            comment.delete()
            return JsonResponse({"success": True})

    return render(request, 'english/profile.html', {'comment_form': form, 'comments': comments})


def logout_view(request):
    logout(request)
    return redirect('/')


def buy_tariff(request, tariff_id):
    tariff = get_object_or_404(CourseTariff, id=tariff_id)
    course = tariff.course

    user_authenticated = request.user.is_authenticated

    if request.method == "POST":
        if not user_authenticated:
            messages.error(request, "Авторизуйтесь, чтобы купить тариф.")
            return redirect("login")  # или можно остаться на той же странице

        receipt = request.FILES.get("receipt")
        if not receipt:
            messages.error(request, "Пожалуйста, загрузите скриншот чека.")
            return render(request, "english/buy_tariff.html", {"tariff": tariff, "user_authenticated": user_authenticated})

        Payment.objects.create(
            user=request.user,
            tariff=tariff,
            amount=tariff.price,
            receipt=receipt,
            status="pending"
        )
        messages.success(request, f"Платеж за тариф '{tariff.name}' отправлен на проверку. Проверьте статус в профиле.")
        return redirect("profile")

    # Другие тарифы курса, кроме текущего
    other_tariffs = course.tariffs.exclude(id=tariff.id)

    context = {
        "tariff": tariff,
        "other_tariffs": other_tariffs,
        "user_authenticated": user_authenticated,
    }
    return render(request, "english/buy_tariff.html", context)


def exercise_view(request, pk):
    exercise = Exercise.objects.get(pk=pk)
    questions = exercise.questions.all()

    for q in questions:
        q.rendered_text = q.render_with_inputs()

    return render(request, "exercise.html", {"exercise": exercise, "questions": questions})


@login_required
def control_test(request, chapter_id):
    """Контрольная работа — доступ только авторизованным пользователям"""
    chapter = get_object_or_404(Chapter, id=chapter_id)
    exercises = Exercise.objects.filter(topic__chapter=chapter).prefetch_related('questions')
    all_questions = Question.objects.filter(exercise__in=exercises).distinct()

    # --- POST: проверка ответов ---
    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        results = {}
        user_answers_dict = {}
        correct_answers_dict = {}

        selected_questions = request.session.get('control_questions', [])
        for q_id in selected_questions:
            q = get_object_or_404(Question, id=q_id)

            # Получаем все ответы пользователя по бланкам
            blanks = {
                k.split('_')[-1]: v.strip()
                for k, v in request.POST.items()
                if k.startswith(f"q_{q.id}_blank")
            }

            # Пропускаем пустые
            if not any(blanks.values()):
                continue

            correct = q.correct_answer or {}
            correct_answers_dict[q_id] = correct

            # Проверяем правильность
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

        # --- Подсчёт результата ---
        total_questions = len(selected_questions)
        correct_count = sum(1 for r in results.values() if r)
        score = (correct_count / total_questions * 100) if total_questions > 0 else 0

        # --- Обновляем статус главы ---
        user_chapter, _ = UserChapter.objects.get_or_create(user=request.user, chapter=chapter)
        user_chapter.completion_score = score
        user_chapter.save()

        next_chapter_id = None
        if score >= 80:
            user_chapter.is_open = True
            user_chapter.save()

            next_chapter = Chapter.objects.filter(
                course=chapter.course,
                order_index=chapter.order_index + 1
            ).first()

            if next_chapter:
                next_user_chapter, _ = UserChapter.objects.get_or_create(
                    user=request.user,
                    chapter=next_chapter
                )
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

    # --- GET: формируем тест ---
    selected_questions = random.sample(list(all_questions), min(20, all_questions.count()))
    request.session['control_questions'] = [q.id for q in selected_questions]

    # Рендерим вопросы
    for q in selected_questions:
        q.rendered_text = q.render_with_inputs()

    context = {
        "chapter": chapter,
        "questions": selected_questions,
        "course": chapter.course,
    }
    return render(request, "english/control_test.html", context)
