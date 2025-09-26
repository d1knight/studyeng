from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(Course)
admin.site.register(CourseTariff)
admin.site.register(Payment)
admin.site.register(User)
admin.site.register(Chapter)
admin.site.register(Topic)
admin.site.register(Exercise)
admin.site.register(Question)

