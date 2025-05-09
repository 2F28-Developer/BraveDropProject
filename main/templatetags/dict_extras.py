from django import template

register = template.Library()

@register.filter
def dict_get(dictionary, key):
    """Return dictionary[key] if it exists, otherwise None."""
    if not dictionary:
        return None
    return dictionary.get(key, None)
