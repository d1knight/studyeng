from django.apps import AppConfig


class EnglishConfig(AppConfig):  # Имя класса должно совпадать с вашим приложением
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'english'  # Имя вашего приложения
    verbose_name = 'English Learning Platform'
    
    def ready(self):
        """
        Метод вызывается при запуске Django.
        Здесь импортируем сигналы для их регистрации.
        """
        # Импортируем signals.py при запуске приложения
        try:
            import english.signals  # Замените 'english' на имя вашего приложения
            print("✅ Signals registered successfully!")
        except ImportError as e:
            print(f"⚠️ Warning: Could not import signals: {e}")