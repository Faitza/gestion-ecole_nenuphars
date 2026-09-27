# core/templatetags/texte.py
# Typographie française : pas de retour à la ligne juste avant « : », « ; »,
# « ! », « ? » ou « » », ni juste après « « » (on les colle avec une espace insécable).
import re

from django import template

register = template.Library()


@register.filter
def insecables(texte):
    texte = re.sub(r" ([:;!?»])", " \\1", str(texte))
    return re.sub(r"« ", "« ", texte)
