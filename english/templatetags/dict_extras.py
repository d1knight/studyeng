# english/templatetags/dict_extras.py
from django import template

register = template.Library()

@register.filter
def dict_get(d, key):
    """Возвращает значение из словаря по ключу, если существует"""
    if isinstance(d, dict):
        return d.get(key)
    return None
