# Adresses servies à l'adresse principale (voir plateforme/middleware.py)
from django.urls import include, path

urlpatterns = [
    path("", include("plateforme.urls")),
]
