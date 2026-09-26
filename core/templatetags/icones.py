# core/templatetags/icones.py
# {% icone "eleves" %} affiche une icône du fichier static/icones/icones.svg.
from django import template
from django.templatetags.static import static
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def icone(nom, classe=""):
    return format_html(
        '<svg class="icone {}" aria-hidden="true" focusable="false"><use href="{}#{}"></use></svg>',
        classe, static("icones/icones.svg"), nom,
    )
