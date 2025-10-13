import re
from django.utils import timezone
from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from ckeditor_uploader.fields import RichTextUploadingField
from django.utils.safestring import mark_safe
import json

# ===================== Пользователи =====================
class UserManager(BaseUserManager):
    def create_user(self, phone_number, first_name, last_name, tg_id, password=None, **extra_fields):
        """Создание обычного пользователя"""
        if not phone_number:
            raise ValueError('Users must have a phone number')

        user = self.model(
            phone_number=phone_number,
            first_name=first_name,
            last_name=last_name,
            tg_id=tg_id,
            **extra_fields
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, first_name, last_name, tg_id, password=None, **extra_fields):
        """Создание суперпользователя"""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(
            phone_number=phone_number,
            first_name=first_name,
            last_name=last_name,
            tg_id=tg_id,
            password=password,
            **extra_fields
        )


class User(AbstractBaseUser, PermissionsMixin):
    """Модель пользователя"""
    id = models.BigAutoField(primary_key=True)
    first_name = models.CharField(max_length=255, verbose_name='Имя')
    last_name = models.CharField(max_length=255, verbose_name='Фамилия')
    phone_number = models.CharField(max_length=255, unique=True, verbose_name='Номер телефона')
    tg_id = models.IntegerField(unique=True, verbose_name='Telegram ID')

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, verbose_name="Доступ в админку")
    is_superuser = models.BooleanField(default=False, verbose_name="Суперпользователь")

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'tg_id']

    class Meta:
        db_table = 'users'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone_number})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class Comment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Пользователь")
    text = models.TextField(verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.text[:20]}"

# ===================== Курсы =====================
class Course(models.Model):
    """Модель курса"""
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, verbose_name='Название курса')
    description = models.TextField(verbose_name='Описание курса')

    class Meta:
        db_table = 'courses'
        verbose_name = 'Курс'
        verbose_name_plural = 'Курсы'
        ordering = ['name']

    def __str__(self):
        return self.name


class CourseTariff(models.Model):
    """Модель тарифа курса"""
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, verbose_name='Название тарифа')
    description = models.TextField(verbose_name='Описание')
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='tariffs',
        verbose_name='Курс'
    )
    price = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        verbose_name='Цена',
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    class Meta:
        db_table = 'course_tariff'
        verbose_name = 'Тариф курса'
        verbose_name_plural = 'Тарифы курсов'
        unique_together = ['course', 'name']

    def __str__(self):
        return f"{self.course.name} - {self.name} ({self.price} сум.)"


class Chapter(models.Model):
    """Модель главы курса"""
    id = models.BigAutoField(primary_key=True)
    order_index = models.BigIntegerField(
        verbose_name='Порядковый номер',
        validators=[MinValueValidator(1)]
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='chapters',
        verbose_name='Курс'
    )
    name = models.CharField(max_length=255, verbose_name='Название главы')
    passing_ball = models.IntegerField(
        verbose_name='Проходной балл',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    class Meta:
        db_table = 'chapter'
        verbose_name = 'Глава'
        verbose_name_plural = 'Главы'
        unique_together = ['course', 'order_index']
        ordering = ['course', 'order_index']

    def __str__(self):
        return f"{self.course.name} - {self.name}"


class Topic(models.Model):
    """Модель темы в главе"""
    id = models.BigAutoField(primary_key=True)
    order_index = models.BigIntegerField(
        verbose_name='Порядковый номер',
        validators=[MinValueValidator(1)]
    )
    is_public = models.BooleanField(default=False, verbose_name='Публичная тема')
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name='topics',
        verbose_name='Глава'
    )
    name = models.CharField(max_length=255, verbose_name='Название темы')
    video_path = models.CharField(max_length=255, verbose_name='Путь к видео')
    content = RichTextUploadingField(verbose_name="Содержание")

    class Meta:
        db_table = 'topic'
        verbose_name = 'Тема'
        verbose_name_plural = 'Темы'
        unique_together = ['chapter', 'order_index']
        ordering = ['chapter', 'order_index']

    def __str__(self):
        return f"{self.chapter.name} - {self.name}"


class Exercise(models.Model):
    """Модель упражнения"""
    EXERCISE_TYPES = [
        ('text_input', 'Ввод текста'),
        ('textarea_input', 'Ввод Эссе'),
        ('fill_blanks', 'Текст с пропусками'),
    ]

    id = models.BigAutoField(primary_key=True)
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='exercises',
        verbose_name='Тема'
    )
    order_index = models.IntegerField(
        verbose_name='Порядковый номер',
        validators=[MinValueValidator(1)]
    )
    exercise_type = models.CharField(
        max_length=255,
        choices=EXERCISE_TYPES,
        verbose_name='Тип упражнения'
    )
    instruction = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Задание',
        help_text="Например: Заполни пропуски правильной формой глагола."
    )

    class Meta:
        db_table = 'exercises'
        verbose_name = 'Упражнение'
        verbose_name_plural = 'Упражнения'
        unique_together = ['topic', 'order_index']
        ordering = ['topic', 'order_index']

    def __str__(self):
        return f"{self.topic.name} - Упражнение {self.order_index}"





class Question(models.Model):
    """Модель вопроса в упражнении"""
    id = models.BigAutoField(primary_key=True)
    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='Упражнение'
    )
    text = models.TextField(
        verbose_name='Текст вопроса',
        help_text='Используйте ___ для обозначения пропусков (например: "I ___ a student.").'
    )
    raw_answers = models.TextField(
        verbose_name='Правильные ответы',
        help_text='Формат: blank1: answer1, answer2\nblank2: answer3\n... (по одному пропуску на строку)',
        blank=True
    )
    correct_answer = models.JSONField(
        verbose_name='Правильные ответы (JSON)',
        help_text='Автоматически формируется из поля "Правильные ответы".',
        blank=True,
        null=True
    )

    class Meta:
        db_table = 'questions'
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'

    def __str__(self):
        return f"Вопрос к {self.exercise}"

    def save(self, *args, **kwargs):
        """Преобразование raw_answers в JSON для correct_answer"""
        if self.raw_answers:
            correct_answer = {}
            lines = self.raw_answers.strip().split('\n')
            for index, line in enumerate(lines, 1):
                if ':' in line:
                    blank, answers = line.split(':', 1)
                    blank = blank.strip()
                    answers = [ans.strip() for ans in answers.split(',') if ans.strip()]
                    if answers:
                        correct_answer[f"blank{index}"] = answers if len(answers) > 1 else answers[0]
                else:
                    correct_answer[f"blank{index}"] = line.strip()
            self.correct_answer = correct_answer
        else:
            self.correct_answer = {}
        super().save(*args, **kwargs)

    def get_correct_answers_list(self):
        """Вернуть список правильных ответов"""
        if not self.correct_answer:
            return []
        result = []
        for k, v in self.correct_answer.items():
            if isinstance(v, list):
                result.append(f"{k} = {', '.join(v)}")
            else:
                result.append(f"{k} = {v}")
        return result

    def formatted_correct_answers(self):
        """Красивый вывод правильных ответов для админки"""
        return "; ".join(self.get_correct_answers_list())

    formatted_correct_answers.short_description = "Правильные ответы"

    def render_with_inputs(self):
        """Рендеринг текста вопроса с input-полями для пропусков"""
        def replacer(match):
            # Генерируем имя blank на основе порядка (blank1, blank2, ...)
            blank_index = len(re.findall(r'___', self.text[:match.start()])) + 1
            blank_name = f"blank{blank_index}"
            return f"<input type='text' name='q_{self.id}_{blank_name}' class='form-control d-inline w-auto' placeholder='...' />"

        rendered = re.sub(r'___', replacer, self.text)
        return mark_safe(rendered)

    def check_user_answer(self, user_answer: dict) -> bool:
        """Проверка правильности ответа (без сохранения)"""
        correct = self.correct_answer or {}
        if not isinstance(user_answer, dict):
            return False
        return all(
            str(user_answer.get(k, "")).strip().lower() in [str(v).strip().lower() for v in (correct.get(k) or [])]
            if isinstance(correct.get(k), list)
            else str(user_answer.get(k, "")).strip().lower() == str(correct.get(k)).strip().lower()
            for k in correct.keys()
        )


# ===================== Прогресс и ответы =====================
class UserChapter(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_chapters',
        verbose_name='Пользователь'
    )
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name='user_chapters',
        verbose_name='Глава'
    )
    is_active = models.BooleanField(default=False, verbose_name='Активная глава')
    is_open = models.BooleanField(default=False, verbose_name='Открытая глава')
    completion_score = models.FloatField(default=0.0, verbose_name='Процент выполнения')

    class Meta:
        db_table = 'users_and_chapters'
        verbose_name = 'Пользователь и глава'
        verbose_name_plural = 'Пользователи и главы'
        unique_together = ['user', 'chapter']
        indexes = [
            models.Index(fields=['user', 'chapter']),
        ]  # Опционально для производительности

    def __str__(self):
        return f"{self.user.full_name} - {self.chapter.name}"

class UserQuestion(models.Model):
    """Ответы пользователя"""
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_answers',
        verbose_name='Пользователь'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='user_answers',
        verbose_name='Вопрос'
    )
    user_answer = models.JSONField(
        verbose_name='Ответ пользователя',
        help_text='Формат: {"blank1": "is", "blank2": "are"}'
    )
    is_correct = models.BooleanField(null=True, blank=True, verbose_name='Правильный ответ')
    answered_at = models.DateTimeField(auto_now_add=True, verbose_name='Время ответа')

    class Meta:
        db_table = 'users_and_questions'
        verbose_name = 'Ответ пользователя'
        verbose_name_plural = 'Ответы пользователей'
        unique_together = ['user', 'question']
        ordering = ['-answered_at']

    def __str__(self):
        return f"{self.user.full_name} - {self.question}"

    def check_answer(self):
        correct = self.question.correct_answer
        if isinstance(self.user_answer, dict):
            self.is_correct = all(
                str(self.user_answer.get(k, "")).strip().lower() in [str(v).strip().lower() for v in (correct.get(k) or [])]
                if isinstance(correct.get(k), list)
                else str(self.user_answer.get(k, "")).strip().lower() == str(correct.get(k)).strip().lower()
                for k in correct.keys()
            )
        else:
            self.is_correct = False
        self.save()
        return self.is_correct


# ===================== Платежи =====================
class Payment(models.Model):
    """Модель платежа"""
    PAYMENT_STATUSES = [
        ('pending', 'Ожидает оплаты'),
        ('paid', 'Оплачен'),
        ('failed', 'Ошибка'),
        ('cancelled', 'Отменен'),
        ('refunded', 'Возвращен'),
    ]

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Пользователь'
    )
    amount = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        verbose_name='Сумма',
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    create_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    receipt = models.ImageField(upload_to='receipts/', verbose_name='Скриншот чека')
    status = models.CharField(
        max_length=255,
        choices=PAYMENT_STATUSES,
        default='pending',
        verbose_name='Статус платежа'
    )
    tariff = models.ForeignKey(
        CourseTariff,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Тариф'
    )

    class Meta:
        db_table = 'payment'
        verbose_name = 'Платеж'
        verbose_name_plural = 'Платежи'
        ordering = ['-create_at']

    def __str__(self):
        return f"Платеж {self.id} - {self.user.full_name} ({self.amount} сум., {self.get_status_display()})"
