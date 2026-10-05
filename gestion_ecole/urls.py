"""URL configuration for gestion_ecole project."""
from django.contrib import admin
from django.urls import path, include

from core.views_sante import sante

urlpatterns = [
    path('admin/', admin.site.urls),
    # Surveillée par l'alerte « site en panne » (voir docs/production.md)
    path('sante/', sante, name='sante'),
    # Site public (accueil, admissions, contact...), puis connexion et gestion (/gestion/)
    path('', include('site_public.urls')),
    path('', include('core.urls')),
]
# Les pages d'erreur sont templates/400.html, 403.html, 404.html et 500.html
