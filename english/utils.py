import random
import re
from django.core.cache import cache
from django.utils.safestring import mark_safe

def generate_unique_otp(length=6):
    """
    Generates a random OTP that is not currently in the cache.
    """
    while True:
        code = ''.join([str(random.randint(0, 9)) for _ in range(length)])
        # Check if this code is already used as a key
        if not cache.get(f"code_{code}"):
            return code



def render_question(text):
    """
    Находит {{blankX:вариант1|вариант2}} и заменяет на <input> с правильными ответами
    """
    def replacer(match):
        field_name = match.group(1)  # например blank1
        answers = match.group(2)     # am|’m
        return f'<input type="text" name="{field_name}" class="answer-field form-control d-inline w-auto" data-correct="{answers}">'

    rendered = re.sub(r"\{\{(blank\d+):(.*?)\}\}", replacer, text)
    return mark_safe(rendered)



