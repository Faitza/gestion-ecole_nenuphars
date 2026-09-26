from django import template
from django.urls import reverse
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def photo(personne, taille="petite"):
    """Photo d'un élève, d'un professeur ou d'un employé, ou ses initiales s'il n'en a pas."""
    if personne.photo:
        url = reverse("core:photo", args=[personne._meta.model_name, personne.pk])
        # Le nom du fichier change à chaque nouvelle photo : le navigateur ne garde pas l'ancienne
        version = personne.photo.name.rsplit("/", 1)[-1][:8]
        return format_html('<img src="{}?v={}" alt="" class="photo {}" loading="lazy">', url, version, taille)
    initiales = f"{personne.prenom[:1]}{personne.nom[:1]}".upper()
    return format_html('<span class="photo {} initiales" aria-hidden="true">{}</span>', taille, initiales)
