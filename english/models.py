from django.utils import timezone
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class UserManager(BaseUserManager):
    def create_user(self, phone_number, first_name, last_name, tg_id, password=None, **extra_fields):
        """
        Создание обычного пользователя
        """
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
            user.set_password(password)   # если пароль указан
        else:
            user.set_unusable_password()  # если пароля нет
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, first_name, last_name, tg_id, password=None, **extra_fields):
        """
        Создание суперпользователя (для админки)
        """
        extra_fields.setdefault("is_staff", True)       # 🔹 обязательно
        extra_fields.setdefault("is_superuser", True)   # 🔹 обязательно
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

    # 🔹 Обязательные для Django поля
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
        max_digits=8, 
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
    content = models.TextField(verbose_name='Содержание')
    
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
    text = models.TextField(verbose_name='Текст вопроса')
    correct_answer = models.JSONField(verbose_name='Правильный ответ')
    
    class Meta:
        db_table = 'questions'
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
    
    def __str__(self):
        return f"Вопрос к {self.exercise}"


class UserChapter(models.Model):
    """Модель связи пользователя с главой"""
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
    
    class Meta:
        db_table = 'users_and_chapters'
        verbose_name = 'Пользователь и глава'
        verbose_name_plural = 'Пользователи и главы'
        unique_together = ['user', 'chapter']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.chapter.name}"


class UserQuestion(models.Model):
    """Модель ответов пользователя на вопросы"""
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
    user_answer = models.TextField(verbose_name='Ответ пользователя')
    is_correct = models.BooleanField(null=True, blank=True, verbose_name='Правильный ответ')
    answered_at = models.DateTimeField(verbose_name='Время ответа')
    
    class Meta:
        db_table = 'users_and_questions'
        verbose_name = 'Ответ пользователя'
        verbose_name_plural = 'Ответы пользователей'
        unique_together = ['user', 'question']
        ordering = ['-answered_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.question}"

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
        'User',
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Пользователь'
    )
    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name='Сумма',
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    create_at = models.DateTimeField(
        auto_now_add=True,  # ✅ автоматически ставится при создании записи
        verbose_name='Дата создания'
    )
    receipt = models.CharField(max_length=255, verbose_name='Чек')
    status = models.CharField(
        max_length=255,
        choices=PAYMENT_STATUSES,
        default='pending',
        verbose_name='Статус платежа'
    )
    tariff = models.ForeignKey(
        'CourseTariff',
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
        return f"Платеж {self.receipt} - {self.user.full_name} ({self.amount} сум.)"

