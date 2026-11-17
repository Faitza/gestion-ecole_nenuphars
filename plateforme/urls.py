# plateforme/urls.py
# Adresses de la plateforme (adresse principale, SAAS_DOMAINE). Les écoles, elles,
# utilisent gestion_ecole/urls.py (voir plateforme/middleware.py).
from django.urls import path

from core.views_sante import sante

from . import views

app_name = "plateforme"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("connexion/", views.ConnexionView.as_view(), name="connexion"),
    path("deconnexion/", views.DeconnexionView.as_view(), name="deconnexion"),
    path("ecoles/", views.liste, name="ecoles"),
    path("ecoles/nouvelle/", views.nouvelle, name="nouvelle"),
    path("ecoles/<int:pk>/", views.modifier, name="modifier"),
    path("ecoles/<int:pk>/etat/", views.changer_etat, name="changer_etat"),
    path("sante/", sante, name="sante"),
]
