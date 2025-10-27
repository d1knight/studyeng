import datetime
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
from datetime import datetime
from django.db import IntegrityError


def main_page(request):
    courses = Course.objects.all()
    tariffs = CourseTariff.objects.all()
    comment_form = CommentForm()

    # Обработка POST запроса (добавление комментария - только для авторизованных)
    if request.method == "POST":
        if not request.user.is_authenticated:
            # Для AJAX запросов
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "success": False, 
                    "error": "Войдите, чтобы оставить комментарий."
                })
            # Для обычных запросов
            messages.error(request, "Войдите, чтобы оставить комментарий.")
        else:
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.user = request.user
                comment.save()
                
                # Обработка AJAX запроса
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    avatar_url = None
                    
                    # Проверяем ТОЛЬКО загруженный аватар
                    if request.user.avatar:
                        avatar_url = request.user.avatar.url
                    
                    return JsonResponse({
                        "success": True,
                        "user": request.user.full_name,
                        "text": comment.text,
                        "avatar_url": avatar_url  # None если нет загруженного аватара
                    })
                
                # Обычный POST запрос
                messages.success(request, "Комментарий добавлен!")
                comment_form = CommentForm()

    # Комментарии видны ВСЕМ
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

        # Проверяем, есть ли оплаченный тариф
        has_paid_access = False
        if user:
            has_paid_access = user.payments.filter(tariff__course=course, status="paid").exists()

        for chapter in chapters:
            # Определяем, открыта ли глава
            is_chapter_open = False
            curr_user_chapter = None

            if chapter.order_index == 1:
                # Первая глава ВСЕГДА открыта для всех
                is_chapter_open = True
                
                if user:
                    user_chapter, created = UserChapter.objects.get_or_create(user=user, chapter=chapter)
                    if created or not user_chapter.is_open:
                        user_chapter.is_open = True
                        user_chapter.save()
                    curr_user_chapter = user_chapter
                else:
                    curr_user_chapter = SimpleNamespace(is_open=True, completion_score=None)
            
            else:
                # Для остальных глав
                if user:
                    user_chapter, created = UserChapter.objects.get_or_create(user=user, chapter=chapter)
                    
                    if created:
                        user_chapter.is_open = False
                    
                    # Проверяем, является ли глава платной
                    if chapter.is_paid and not has_paid_access:
                        # Платная глава закрыта без оплаты
                        is_chapter_open = False
                    else:
                        # Проверяем предыдущую главу
                        prev_chapter = Chapter.objects.filter(
                            course=course, 
                            order_index=chapter.order_index - 1
                        ).first()
                        
                        if prev_chapter:
                            prev_user_chapter = user.user_chapters.filter(chapter=prev_chapter).first()
                            
                            # Открываем главу, если предыдущая пройдена на ≥80%
                            if (prev_user_chapter and 
                                prev_user_chapter.completion_score is not None and 
                                prev_user_chapter.completion_score >= 80):
                                if not user_chapter.is_open:
                                    user_chapter.is_open = True
                                    user_chapter.save()
                                is_chapter_open = True
                            else:
                                is_chapter_open = user_chapter.is_open
                        else:
                            is_chapter_open = user_chapter.is_open
                    
                    curr_user_chapter = user_chapter
                else:
                    is_chapter_open = False
                    curr_user_chapter = SimpleNamespace(is_open=False, completion_score=None)

            # Создаем список тем с атрибутом is_accessible
            chapter.topics_list = []
            for topic in chapter.topics.all().order_by('order_index'):
                # Темы доступны если глава открыта И (глава бесплатная ИЛИ есть оплата)
                if chapter.is_paid:
                    topic.is_accessible = is_chapter_open and has_paid_access
                else:
                    topic.is_accessible = is_chapter_open
                chapter.topics_list.append(topic)

            # Контрольная работа доступна всем авторизованным с открытой главой
            # Для платных глав нужна оплата
            if chapter.is_paid:
                chapter.control_test_accessible = bool(is_chapter_open and user and has_paid_access)
            else:
                chapter.control_test_accessible = bool(is_chapter_open and user)

            # Добавляем информацию о платности главы
            chapter.requires_payment = chapter.is_paid and not has_paid_access

            chapter_user_chapters.append((chapter, curr_user_chapter))

        context = {
            'course': course,
            'chapter_user_chapters': chapter_user_chapters,
            'chapters': chapters,
            'courses': Course.objects.all(),
            'user_has_tariff': has_paid_access if user else False,
        }
        return render(request, 'english/course.html', context)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return HttpResponse(f"Error: {str(e)}", status=500)


def buy_tariff(request, tariff_id):
    tariff = get_object_or_404(CourseTariff, id=tariff_id)
    course = tariff.course

    user_authenticated = request.user.is_authenticated

    if request.method == "POST":
        if not user_authenticated:
            messages.error(request, "Авторизуйтесь, чтобы купить тариф.")
            return redirect("login")

        # Если тариф бесплатный
        if tariff.is_free():
            payment = Payment.objects.create(
                user=request.user,
                tariff=tariff,
                amount=0,
                status="paid"  # Бесплатный тариф сразу активен
            )

            # Создаём записи UserChapter
            for chapter in course.chapters.all():
                user_chapter, created = UserChapter.objects.get_or_create(
                    user=request.user, 
                    chapter=chapter,
                    defaults={'is_open': chapter.order_index == 1}
                )

            cache.clear()
            messages.success(request, f"Тариф '{tariff.name}' успешно активирован! Начните с первой главы!")
            return redirect("profile")
        
        # Если тариф платный
        receipt = request.FILES.get("receipt")
        if not receipt:
            messages.error(request, "Пожалуйста, загрузите скриншот чека.")
            return render(request, "english/buy_tariff.html", {
                "tariff": tariff,
                "user_authenticated": user_authenticated
            })

        payment = Payment.objects.create(
            user=request.user,
            tariff=tariff,
            amount=tariff.price,
            receipt=receipt,
            status="pending"  # Ожидает проверки администратором
        )

        messages.info(request, f"Ваш платеж отправлен на проверку. Администратор проверит чек и активирует тариф '{tariff.name}'.")
        return redirect("profile")

    # Другие тарифы курса
    other_tariffs = course.tariffs.exclude(id=tariff.id)

    context = {
        "tariff": tariff,
        "other_tariffs": other_tariffs,
        "user_authenticated": user_authenticated,
    }
    return render(request, "english/buy_tariff.html", context)


def topic_detail(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    user = request.user if request.user.is_authenticated else None
    chapter = topic.chapter

    # Проверка доступа
    allowed = False
    error_message = ""

    if chapter.order_index == 1:
        allowed = True
    elif user:
        user_chapter = user.user_chapters.filter(chapter=chapter).first()
        has_paid = user.payments.filter(tariff__course=chapter.course, status="paid").exists()

        if not has_paid:
            error_message = "Требуется оплатить тариф для доступа к этой теме."
        elif not user_chapter:
            error_message = "Глава не найдена для пользователя."
        elif not user_chapter.is_open:
            error_message = "Глава закрыта. Завершите предыдущую главу с результатом 80% или выше."
        else:
            allowed = True
    else:
        error_message = "Авторизуйтесь и купите тариф для доступа к темам после 1-й главы."

    if not allowed:
        messages.info(request, error_message)
        return redirect('course_detail', course_id=chapter.course.id)

    # Извлечение упражнений с явной сортировкой
    exercises = Exercise.objects.filter(topic=topic).prefetch_related("questions").order_by('order_index')
    
    # Очистка кэша для данной темы
    from django.core.cache import cache
    cache_key = f"exercises_for_topic_{topic_id}"
    cache.delete(cache_key)

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
        "courses": Course.objects.all(),
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
    first_name = data.get("first_name") or ""
    last_name = data.get("last_name") or ""

    if not phone_number or not tg_id:
        return JsonResponse({"error": "phone_number and tg_id are required"}, status=HTTPStatus.BAD_REQUEST)

    user = User.objects.filter(tg_id=tg_id).first()
    if user:
        user.phone_number = phone_number
        user.first_name = first_name
        user.last_name = last_name
        user.save()
    else:
        user, created = User.objects.get_or_create(
            phone_number=phone_number,
            defaults={'tg_id': tg_id, 'first_name': first_name, 'last_name': last_name},
        )
        if created:
            user.set_unusable_password()
            user.save()

    otp_code = generate_unique_otp()
    cache.set(f"code_{otp_code}", {'phone_number': phone_number}, timeout=60)

    return JsonResponse({"code": otp_code}, status=HTTPStatus.OK)


@login_required
def profile(request):
    # Получаем комментарии пользователя
    comments = Comment.objects.filter(user=request.user).order_by('-created_at')

    # Получаем оплаченные тарифы и связанные курсы
    payments = Payment.objects.filter(user=request.user, status="paid")
    courses = Course.objects.filter(tariffs__in=payments.values('tariff')).distinct()

    # Вычисляем прогресс для каждого курса
    courses_data = []
    for course in courses:
        total_chapters = course.chapters.count()
        completed_chapters = UserChapter.objects.filter(
            user=request.user,
            chapter__course=course,
            completion_score__gte=80
        ).count()
        progress = (completed_chapters / total_chapters * 100) if total_chapters > 0 else 0
        courses_data.append({
            'course': course,
            'progress': round(progress, 1),
            'tariff': payments.filter(tariff__course=course).first().tariff if payments.filter(tariff__course=course).exists() else None
        })

    # Обработка загрузки аватара
    if request.method == "POST" and 'avatar' in request.FILES:
        avatar_file = request.FILES['avatar']
        request.user.avatar = avatar_file
        request.user.save()
        return redirect('profile')

    # Обработка формы добавления комментария
    if request.method == "POST" and not request.headers.get("x-requested-with") == "XMLHttpRequest":
        if "add_comment" in request.POST:
            form = CommentForm(request.POST)
            if form.is_valid():
                new_comment = form.save(commit=False)
                new_comment.user = request.user
                new_comment.save()
                return redirect('profile')
        else:
            form = CommentForm()
    else:
        form = CommentForm()

    # Обработка AJAX-запросов для редактирования и удаления комментариев
    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
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
        elif "delete_comment" in request.POST:
            comment_id = request.POST.get("comment_id")
            comment = get_object_or_404(Comment, id=comment_id, user=request.user)
            comment.delete()
            return JsonResponse({"success": True})

    context = {
        'comment_form': form,
        'comments': comments,
        'courses_data': courses_data,
    }
    return render(request, 'english/profile.html', context)

def logout_view(request):
    logout(request)
    return redirect('/')

def buy_tariff(request, tariff_id):
    tariff = get_object_or_404(CourseTariff, id=tariff_id)
    course = tariff.course
    courses = Course.objects.all()

    user_authenticated = request.user.is_authenticated

    # Если тариф бесплатный - перенаправляем на курс напрямую
    # Не нужно "активировать" бесплатный тариф
    if tariff.is_free() and user_authenticated:
        messages.info(request, f"Курс '{course.name}' бесплатный! Просто начните обучение.")
        return redirect('course_detail', course_id=course.id)

    if request.method == "POST":
        if not user_authenticated:
            messages.error(request, "Авторизуйтесь, чтобы купить тариф.")
            return redirect("login")

        receipt = request.FILES.get("receipt")
        if not receipt:
            messages.error(request, "Пожалуйста, загрузите скриншот чека.")
            return render(request, "english/buy_tariff.html", {
                "tariff": tariff, 
                "user_authenticated": user_authenticated,
                "courses": courses
            })

        # Создаём платёж со статусом pending (ожидает проверки)
        payment = Payment.objects.create(
            user=request.user,
            tariff=tariff,
            amount=tariff.price,
            receipt=receipt,
            status="pending"  # Администратор проверит и изменит на "paid"
        )

        messages.info(request, f"Ваш платёж отправлен на проверку. Администратор проверит чек и активирует тариф '{tariff.name}'.")
        return redirect("profile")

    # Другие тарифы курса
    other_tariffs = course.tariffs.exclude(id=tariff.id)

    context = {
        "tariff": tariff,
        "other_tariffs": other_tariffs,
        "user_authenticated": user_authenticated,
        "courses": courses,
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
    
    # Проверка доступа - только авторизация и открытая глава
    user_chapter = request.user.user_chapters.filter(chapter=chapter).first()
    if not user_chapter or not user_chapter.is_open:
        messages.error(request, "Эта глава пока закрыта. Завершите предыдущую главу с результатом 80% или выше.")
        return redirect('course_detail', course_id=chapter.course.id)
    
    exercises = Exercise.objects.filter(topic__chapter=chapter).prefetch_related('questions')
    all_questions = Question.objects.filter(exercise__in=exercises).distinct()

    # POST: проверка ответов
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

        # Подсчёт результата
        total_questions = len(selected_questions)
        correct_count = sum(1 for r in results.values() if r)
        score = (correct_count / total_questions * 100) if total_questions > 0 else 0

        # Обновляем статус главы
        user_chapter.completion_score = score
        user_chapter.save()

        next_chapter_id = None
        if score >= 80:
            # Открываем следующую главу
            next_chapter = Chapter.objects.filter(
                course=chapter.course,
                order_index=chapter.order_index + 1
            ).first()

            if next_chapter:
                next_user_chapter, created = UserChapter.objects.get_or_create(
                    user=request.user,
                    chapter=next_chapter
                )
                if not next_user_chapter.is_open:
                    next_user_chapter.is_open = True
                    next_user_chapter.save()
                    next_chapter_id = next_chapter.id
                else:
                    next_chapter_id = next_chapter.id

        return JsonResponse({
            "results": results,
            "user_answers": user_answers_dict,
            "correct_answers": correct_answers_dict,
            "score": score,
            "next_chapter_id": next_chapter_id,
        })

    # GET: формируем тест
    selected_questions = random.sample(list(all_questions), min(20, all_questions.count()))
    request.session['control_questions'] = [q.id for q in selected_questions]

    for q in selected_questions:
        q.rendered_text = q.render_with_inputs()

    context = {
        "chapter": chapter,
        "questions": selected_questions,
        "course": chapter.course,
        "courses": Course.objects.all(),
    }
    return render(request, "english/control_test.html", context)