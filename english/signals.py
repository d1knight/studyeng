from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Payment, UserChapter
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Payment)
def create_user_chapters_on_payment_approval(sender, instance, created, **kwargs):
    """
    Автоматически создаёт записи UserChapter когда админ одобряет платеж.
    Срабатывает при изменении статуса на 'paid'.
    
    Логика:
    - Проверяет, что статус платежа = 'paid'
    - Создаёт UserChapter для всех глав курса
    - Открывает только первую главу (order_index == 1)
    - Остальные главы открываются по мере прохождения
    """
    
    # Проверяем, что статус = 'paid'
    if instance.status == 'paid':
        user = instance.user
        course = instance.tariff.course
        
        # Проверяем, созданы ли уже UserChapter для этого пользователя и курса
        existing_chapters_count = UserChapter.objects.filter(
            user=user,
            chapter__course=course
        ).count()
        
        total_chapters = course.chapters.count()
        
        # Если записей нет или их меньше, чем глав в курсе - создаём/обновляем
        if existing_chapters_count < total_chapters:
            chapters_created = 0
            chapters_updated = 0
            
            for chapter in course.chapters.all().order_by('order_index'):
                user_chapter, was_created = UserChapter.objects.get_or_create(
                    user=user,
                    chapter=chapter,
                    defaults={
                        'is_open': chapter.order_index == 1,  # Только первая глава открыта
                        'is_active': False,
                        'completion_score': 0.0
                    }
                )
                
                if was_created:
                    chapters_created += 1
                    logger.info(f"✅ Created UserChapter: {user.full_name} -> {chapter.name}")
                else:
                    # Если запись уже существовала, но платёж только что одобрен - 
                    # можно обновить is_open для первой главы на всякий случай
                    if chapter.order_index == 1 and not user_chapter.is_open:
                        user_chapter.is_open = True
                        user_chapter.save()
                        chapters_updated += 1
                        logger.info(f"🔓 Opened first chapter for: {user.full_name} -> {chapter.name}")
            
            if chapters_created > 0:
                logger.info(
                    f"🎉 Payment approved! Created {chapters_created} UserChapters "
                    f"for {user.full_name} in course '{course.name}' "
                    f"(Payment ID: {instance.id})"
                )
            
            if chapters_updated > 0:
                logger.info(f"🔄 Updated {chapters_updated} existing UserChapters")
        else:
            logger.info(
                f"ℹ️ UserChapters already exist for {user.full_name} "
                f"in course '{course.name}' (Payment ID: {instance.id})"
            )