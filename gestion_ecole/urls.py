"""URL configuration for gestion_ecole project."""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Site public (accueil, admissions, contact...), puis connexion et gestion (/gestion/)
    path('', include('site_public.urls')),
    path('', include('core.urls')),
]
