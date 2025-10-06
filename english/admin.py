from django.contrib import admin
from django.contrib import messages
from .models import Course, CourseTariff, User, Chapter, Topic, Exercise, Question, Payment, UserChapter

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']

@admin.register(CourseTariff)
class CourseTariffAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'course', 'price']
    list_filter = ['course']
    search_fields = ['name', 'course__name']

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'phone_number', 'first_name', 'last_name', 'tg_id']
    search_fields = ['phone_number', 'first_name', 'last_name']

@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'course', 'order_index']
    list_filter = ['course']
    search_fields = ['name', 'course__name']

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'chapter', 'order_index']
    list_filter = ['chapter']
    search_fields = ['name', 'chapter__name']

@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ['id', 'topic', 'order_index', 'exercise_type']
    list_filter = ['topic', 'exercise_type']
    search_fields = ['topic__name']

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'exercise', 'text']
    list_filter = ['exercise']
    search_fields = ['text']

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
                if chapter.order_index == 1:
                    user_chapter.is_open = True
                else:
                    # Открываем все главы для нового пользователя
                    user_chapter.is_open = True
                user_chapter.save()

            updated += 1

        if updated:
            self.message_user(request, f'Одобрено {updated} платежей. Доступ к курсу активирован.', messages.SUCCESS)
        else:
            self.message_user(request, 'Нет платежей для одобрения.', messages.WARNING)

    approve_payments.short_description = "Одобрить выбранные платежи"

    def reject_payments(self, request, queryset):
        updated = 0
        for payment in queryset.filter(status='pending'):
            payment.status = 'cancelled'
            payment.save()
            updated += 1

        if updated:
            self.message_user(request, f'Отклонено {updated} платежей.', messages.WARNING)
        else:
            self.message_user(request, 'Нет платежей для отклонения.', messages.WARNING)

    reject_payments.short_description = "Отклонить выбранные платежи"

# Регистрация UserChapter (добавим, если нужно кастомизацию)
@admin.register(UserChapter)
class UserChapterAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'chapter', 'is_open', 'completion_score']
    list_filter = ['is_open', 'chapter']
    search_fields = ['user__phone_number', 'chapter__name']