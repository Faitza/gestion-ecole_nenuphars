# core/urls.py
from django.urls import path
from django.views.generic import RedirectView
from . import views, views_professeurs

app_name = "core"

urlpatterns = [
    # Une seule page de connexion pour tout le monde
    path("connexion/", views.LoginView.as_view(), name="login"),
    path("login/", RedirectView.as_view(pattern_name="core:login", query_string=True)),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("mot-de-passe/", views.MotDePasseView.as_view(), name="mot_de_passe"),
    path("espace/", views.espace, name="espace"),
    path("", views.dashboard, name="dashboard"),

    # Élèves
    path("eleves/", views.eleve_liste, name="eleve_liste"),
    path("eleves/nouveau/", views.eleve_creer, name="eleve_creer"),
    path("eleves/<int:pk>/modifier/", views.eleve_modifier, name="eleve_modifier"),
    path("eleves/<int:pk>/supprimer/", views.eleve_supprimer, name="eleve_supprimer"),

    # Classes
    path("classes/", views.classe_liste, name="classe_liste"),
    path("classes/nouveau/", views.classe_creer, name="classe_creer"),
    path("classes/<int:pk>/modifier/", views.classe_modifier, name="classe_modifier"),
    path("classes/<int:pk>/supprimer/", views.classe_supprimer, name="classe_supprimer"),

    # Professeurs
    path("professeurs/", views.professeur_liste, name="professeur_liste"),
    path("professeurs/nouveau/", views_professeurs.professeur_inscrire, name="professeur_creer"),
    path("professeurs/<int:pk>/", views_professeurs.professeur_fiche, name="professeur_fiche"),
    path("professeurs/<int:pk>/modifier/", views.professeur_modifier, name="professeur_modifier"),
    path("professeurs/<int:pk>/supprimer/", views.professeur_supprimer, name="professeur_supprimer"),
    path("professeurs/<int:pk>/acces/", views_professeurs.professeur_acces, name="professeur_acces"),
    path("professeurs/<int:pk>/nouveau-mot-de-passe/", views_professeurs.professeur_nouveau_mot_de_passe,
         name="professeur_nouveau_mot_de_passe"),
    path("professeurs/<int:pk>/classe/", views_professeurs.professeur_affecter, name="professeur_affecter"),
    path("professeurs/<int:pk>/cours/", views_professeurs.professeur_cours, name="professeur_cours"),
    path("professeurs/<int:pk>/valider/", views_professeurs.professeur_valider_cours, name="professeur_valider_cours"),
    path("affectations/<int:pk>/terminer/", views_professeurs.affectation_terminer, name="affectation_terminer"),
    path("cours/<int:pk>/supprimer/", views_professeurs.cours_supprimer, name="cours_supprimer"),

    # Employés
    path("employes/", views.employe_liste, name="employe_liste"),
    path("employes/nouveau/", views.employe_creer, name="employe_creer"),
    path("employes/<int:pk>/modifier/", views.employe_modifier, name="employe_modifier"),
    path("employes/<int:pk>/supprimer/", views.employe_supprimer, name="employe_supprimer"),

    # Paiements
    path("paiements/", views.paiement_liste, name="paiement_liste"),
    path("paiements/nouveau/", views.paiement_creer, name="paiement_creer"),
    path("paiements/<int:pk>/supprimer/", views.paiement_supprimer, name="paiement_supprimer"),

    # Notes
    path("notes/", views.note_liste, name="note_liste"),
    path("notes/nouveau/", views.note_creer, name="note_creer"),
    path("notes/<int:pk>/modifier/", views.note_modifier, name="note_modifier"),
    path("notes/<int:pk>/supprimer/", views.note_supprimer, name="note_supprimer"),
]
