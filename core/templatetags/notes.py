from django import template

register = template.Library()


@register.filter
def note(valeur):
    """Note sur 100 sans zéros inutiles, avec une virgule : 80, 72,5, 72,25."""
    if valeur in (None, ""):
        return ""
    return f"{valeur.normalize():f}".replace(".", ",")
