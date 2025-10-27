from django.contrib import admin, messages
from django import forms
from django.utils.safestring import mark_safe
from .models import (
    Course, CourseTariff, User, Chapter, Topic,
    Exercise, Question, Payment, UserChapter
)
import re

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


    def clean(self):
        cleaned_data = super().clean()
        text = cleaned_data.get('text', '')
        raw_answers = cleaned_data.get('raw_answers', '')
        blank_count = len(re.findall(r'___', text))
        answer_lines = len(raw_answers.strip().split('\n')) if raw_answers.strip() else 0
        if blank_count != answer_lines:
            raise forms.ValidationError(
                f"Количество пропусков (___) в тексте ({blank_count}) должно совпадать с количеством строк в ответах ({answer_lines})."
            )
        return cleaned_data

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
    list_display = ['id', 'name', 'chapter', 'order_index', 'video_preview']
    list_filter = ['chapter']
    search_fields = ['name', 'chapter__name']
    fields = ['chapter', 'order_index', 'is_public', 'name', 'content', 'video']
    inlines = [ExerciseInline]

    def video_preview(self, obj):
        if obj.video:
            return mark_safe(
                f'<video width="220" controls>'
                f'<source src="{obj.video.url}" type="video/mp4">'
                f'</video>'
            )
        return "—"
    video_preview.short_description = "Видео"

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
    list_display = ['id', 'user', 'tariff', 'amount', 'status', 'create_at', 'receipt_link']
    list_filter = ['status', 'create_at']
    search_fields = ['user__phone_number', 'tariff__name']
    actions = ['approve_payments', 'reject_payments']

    def receipt_link(self, obj):
        if obj.receipt:
            return mark_safe(f'<a href="{obj.receipt.url}" target="_blank">Просмотреть чек</a>')
        return "-"
    receipt_link.short_description = "Чек"

    def approve_payments(self, request, queryset):
        updated = 0
        for payment in queryset.filter(status='pending'):
            payment.status = 'paid'
            payment.save()

            # Открываем все главы курса для пользователя
            course = payment.tariff.course
            chapters = course.chapters.all()
            for chapter in chapters:
                user_chapter, created = UserChapter.objects.get_or_create(
                    user=payment.user,
                    chapter=chapter
                )
                user_chapter.is_open = True
                user_chapter.save()

            updated += 1

        if updated:
            self.message_user(request, f'✅ Одобрено {updated} платежей. Доступ к курсу открыт.', messages.SUCCESS)
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