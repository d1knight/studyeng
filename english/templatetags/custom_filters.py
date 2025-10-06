from django import template

register = template.Library()

@register.filter
def dict_get(dict, key):
    """
    Возвращает значение из словаря по ключу.
    """
    return dict.get(str(key))