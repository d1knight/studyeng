from django.contrib import admin, messages
from django import forms
from django.utils.safestring import mark_safe
from .models import (
    Course, CourseTariff, User, Chapter, Topic,
    Exercise, Question, Payment, UserChapter
)

# ===================== Форма для Question =====================
class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['exercise', 'text', 'raw_answers', 'correct_answer']
        widgets = {
            'text': forms.Textarea(attrs={
                'rows': 3,
                'cols': 55,
                'class': 'question-text',
                'placeholder': 'Пример: I ___ a student, and you ___ happy.'
            }),
            'raw_answers': forms.Textarea(attrs={
                'rows': 3,
                'cols': 55,
                'class': 'question-answers',
                'placeholder': 'Пример:\nblank1: am, is\nblank2: are'
            }),
            'correct_answer': forms.Textarea(attrs={
                'rows': 3,
                'cols': 80,
                'class': 'question-json',
                'readonly': 'readonly'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем инструкции в виде HTML
        self.fields['text'].help_text = mark_safe("""
            Используйте <strong>___</strong> для обозначения пропусков.<br>
            <strong>Пример:</strong> I ___ a student, and you ___ happy.<br>
            Каждый ___ будет заменен на поле ввода на странице темы.
        """)
        self.fields['raw_answers'].help_text = mark_safe("""
            Вводите ответы в формате: <code>blank1: ответ1, ответ2\nblank2: ответ3</code><br>
            <strong>Пример:</strong><br>
            <pre style="background: #f8f9fa; padding: 10px; border-radius: 6px;">
blank1: am, is
blank2: are
            </pre>
            Каждый пропуск (___) соответствует строке в этом поле. Если несколько ответов, разделяйте их запятыми.
        """)

# ===================== Inline для Exercise =====================
class ExerciseInline(admin.TabularInline):
    model = Exercise
    extra = 1
    fields = ['order_index', 'exercise_type', 'instruction']
    show_change_link = True

# ===================== Inline для Question =====================
class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    form = QuestionForm
    fields = ['text', 'raw_answers']

# ===================== Course =====================
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']

# ===================== CourseTariff =====================
@admin.register(CourseTariff)
class CourseTariffAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'course', 'price']
    list_filter = ['course']
    search_fields = ['name', 'course__name']

# ===================== User =====================
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'phone_number', 'first_name', 'last_name', 'tg_id']
    search_fields = ['phone_number', 'first_name', 'last_name']

# ===================== Chapter =====================
@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'course', 'order_index']
    list_filter = ['course']
    search_fields = ['name', 'course__name']

# ===================== Topic =====================
@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'chapter', 'order_index']
    list_filter = ['chapter']
    search_fields = ['name', 'chapter__name']
    inlines = [ExerciseInline]

# ===================== Exercise =====================
@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ['id', 'topic', 'order_index', 'exercise_type']
    list_filter = ['topic', 'exercise_type']
    search_fields = ['topic__name']
    inlines = [QuestionInline]

# ===================== Question =====================
@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    form = QuestionForm
    list_display = ['id', 'exercise', 'short_text', 'formatted_correct_answers']
    list_filter = ['exercise__topic', 'exercise']
    search_fields = ['text', 'raw_answers']
    fields = ['exercise', 'text', 'raw_answers', 'correct_answer']
    readonly_fields = ['correct_answer']

    def short_text(self, obj):
        return obj.text[:60] + "..." if len(obj.text) > 60 else obj.text
    short_text.short_description = "Текст вопроса"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('exercise__topic')

    class Media:
        css = {
            'all': ('css/admin_custom.css',)
        }

# ===================== Payment =====================
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'tariff', 'amount', 'status', 'create_at']
    list_filter = ['status', 'create_at']
    search_fields = ['user__phone_number', 'tariff__name']

    actions = ['approve_payments', 'reject_payments']

    def approve_payments(self, request, queryset):
        updated = 0
        for payment in queryset.filter(status='pending'):
            payment.status = 'paid'
            payment.save()

            # Активация доступа к курсу
            course = payment.tariff.course
            chapters = course.chapters.all()
            for chapter in chapters:
                user_chapter, created = UserChapter.objects.get_or_create(
                    user=payment.user,
                    chapter=chapter
                )
                # Открываем все главы для пользователя
                user_chapter.is_open = True
                user_chapter.save()

            updated += 1

        if updated:
            self.message_user(request, f'✅ Одобрено {updated} платежей. Доступ к курсу активирован.', messages.SUCCESS)
        else:
            self.message_user(request, 'Нет платежей для одобрения.', messages.WARNING)

    approve_payments.short_description = "Одобрить выбранные платежи"

    def reject_payments(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='cancelled')
        if updated:
            self.message_user(request, f'❌ Отклонено {updated} платежей.', messages.WARNING)
        else:
            self.message_user(request, 'Нет платежей для отклонения.', messages.WARNING)

    reject_payments.short_description = "Отклонить выбранные платежи"

# ===================== UserChapter =====================
@admin.register(UserChapter)
class UserChapterAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'chapter', 'is_open', 'completion_score']
    list_filter = ['is_open', 'chapter']
    search_fields = ['user__phone_number', 'chapter__name']