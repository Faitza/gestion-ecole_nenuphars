# site_public/urls.py
from django.urls import path

from . import views

app_name = "site"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("ecole/", views.ecole, name="ecole"),
    path("niveaux/", views.niveaux, name="niveaux"),
    path("admissions/", views.admissions, name="admissions"),
    path("admissions/preinscription/", views.preinscription, name="preinscription"),
    path("admissions/preinscription/envoyee/", views.preinscription_envoyee, name="preinscription_envoyee"),
    path("contact/", views.contact, name="contact"),
    path("activites/", views.activites, name="activites"),
    path("activites/<int:pk>/", views.activite, name="activite"),
    path("activites/photos/<int:pk>/<str:taille>/", views.photo_activite, name="photo_activite"),
]
