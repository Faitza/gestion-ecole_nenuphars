# core/urls.py
# La page d'accueil « / » est celle du site public (site_public/urls.py) ;
# la gestion de l'école est sous /gestion/.
from django.urls import include, path
from django.views.generic import RedirectView
from . import (views, views_admissions, views_annonces, views_bulletins, views_fiches, views_notes, views_parents,
               views_professeurs, views_vie_scolaire)

app_name = "core"

gestion = [
    path("", views.dashboard, name="dashboard"),

    # Élèves
    path("eleves/", views.eleve_liste, name="eleve_liste"),
    path("eleves/nouveau/", views.eleve_creer, name="eleve_creer"),
    path("eleves/<int:pk>/", views_fiches.eleve_fiche, name="eleve_fiche"),
    path("eleves/<int:pk>/modifier/", views.eleve_modifier, name="eleve_modifier"),
    path("eleves/<int:pk>/supprimer/", views.eleve_supprimer, name="eleve_supprimer"),
    path("eleves/<int:pk>/acces-parent/", views_parents.eleve_acces_parent, name="eleve_acces_parent"),

    # Classes
    path("classes/", views.classe_liste, name="classe_liste"),
    path("classes/nouveau/", views.classe_creer, name="classe_creer"),
    path("classes/<int:pk>/", views_fiches.classe_fiche, name="classe_fiche"),
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
    path("employes/<int:pk>/", views_fiches.employe_fiche, name="employe_fiche"),
    path("employes/<int:pk>/modifier/", views.employe_modifier, name="employe_modifier"),
    path("employes/<int:pk>/supprimer/", views.employe_supprimer, name="employe_supprimer"),

    # Paiements
    path("paiements/", views.paiement_liste, name="paiement_liste"),
    path("paiements/nouveau/", views.paiement_creer, name="paiement_creer"),
    path("paiements/<int:pk>/supprimer/", views.paiement_supprimer, name="paiement_supprimer"),

    # Photos (seulement pour ceux qui ont le droit de voir la personne)
    path("photos/<str:modele>/<int:pk>/", views_fiches.photo, name="photo"),

    # Préinscriptions envoyées depuis le site public, et messages de la page Contact
    path("preinscriptions/", views_admissions.preinscription_liste, name="preinscription_liste"),
    path("preinscriptions/<int:pk>/", views_admissions.preinscription_fiche, name="preinscription_fiche"),
    path("preinscriptions/<int:pk>/modifier/", views_admissions.preinscription_modifier, name="preinscription_modifier"),
    path("preinscriptions/<int:pk>/etape/", views_admissions.preinscription_etape, name="preinscription_etape"),
    path("preinscriptions/<int:pk>/supprimer/", views_admissions.preinscription_supprimer, name="preinscription_supprimer"),
    path("preinscriptions/<int:pk>/pieces/<str:champ>/", views_admissions.piece, name="piece"),
    # Comptes parents : codes d'accès remis aux familles
    path("parents/", views_parents.parent_liste, name="parent_liste"),
    path("parents/<int:pk>/acces/", views_parents.parent_acces, name="parent_acces"),
    path("parents/<int:pk>/nouveau-code/", views_parents.parent_nouveau_code, name="parent_nouveau_code"),
    path("parents/<int:pk>/nouveau-mot-de-passe/", views_parents.parent_nouveau_mot_de_passe,
         name="parent_nouveau_mot_de_passe"),

    path("messages/", views_admissions.message_liste, name="message_liste"),
    path("messages/<int:pk>/traite/", views_admissions.message_traite, name="message_traite"),

    # Vie scolaire : appel du matin, absences et retards, incidents
    path("vie-scolaire/", views_vie_scolaire.tableau, name="vie_scolaire"),
    path("vie-scolaire/appel/", views_vie_scolaire.appel_choix, name="appel_choix"),
    path("vie-scolaire/appel/<int:pk>/", views_vie_scolaire.appel, name="appel"),
    path("vie-scolaire/absences/<int:pk>/justifier/", views_vie_scolaire.absence_justifier, name="absence_justifier"),
    path("vie-scolaire/malade/", views_vie_scolaire.sante_nouvelle, name="sante_nouvelle"),
    path("vie-scolaire/malade/<int:pk>/", views_vie_scolaire.sante_fiche, name="sante_fiche"),
    path("vie-scolaire/incidents/nouveau/", views_vie_scolaire.incident_nouveau, name="incident_nouveau"),
    path("vie-scolaire/incidents/<int:pk>/", views_vie_scolaire.incident_fiche, name="incident_fiche"),
    path("vie-scolaire/incidents/<int:pk>/convocation/", views_vie_scolaire.incident_convocation,
         name="incident_convocation"),

    # Bulletins trimestriels
    path("bulletins/", views_bulletins.bulletins_liste, name="bulletins_liste"),
    path("bulletins/classes/<int:pk>/", views_bulletins.bulletins_classe, name="bulletins_classe"),
    path("bulletins/classes/<int:pk>/imprimer/", views_bulletins.bulletins_imprimer, name="bulletins_imprimer"),
    path("bulletins/classes/<int:pk>/pdf/", views_bulletins.bulletins_classe_pdf, name="bulletins_classe_pdf"),
    path("bulletins/classes/<int:pk>/eleves/<int:eleve_pk>/", views_bulletins.bulletin_eleve, name="bulletin_eleve"),
    path("bulletins/classes/<int:pk>/eleves/<int:eleve_pk>/<str:format>/", views_bulletins.bulletin_eleve_fichier,
         name="bulletin_eleve_fichier"),

    # Annonces aux parents
    path("annonces/", views_annonces.annonce_liste, name="annonce_liste"),
    path("annonces/nouvelle/", views_annonces.annonce_creer, name="annonce_creer"),
    path("annonces/<int:pk>/modifier/", views_annonces.annonce_modifier, name="annonce_modifier"),
    path("annonces/<int:pk>/supprimer/", views_annonces.annonce_supprimer, name="annonce_supprimer"),

    # Notes
    path("notes/", views.note_liste, name="note_liste"),
    path("notes/saisie/", views_notes.saisie_notes, name="saisie_notes"),
    path("notes/mes-notes/", views_notes.mes_notes, name="mes_notes"),
    path("notes/<int:pk>/modifier/", views.note_modifier, name="note_modifier"),
    path("notes/<int:pk>/supprimer/", views.note_supprimer, name="note_supprimer"),
]

urlpatterns = [
    # Une seule page de connexion pour tout le monde
    path("connexion/", views.LoginView.as_view(), name="login"),
    path("login/", RedirectView.as_view(pattern_name="core:login", query_string=True)),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("mot-de-passe/", views.MotDePasseView.as_view(), name="mot_de_passe"),
    path("espace/", views.espace, name="espace"),
    # Parents : création du compte avec le code de l'école, puis leur espace
    path("inscription/", views_parents.inscription, name="inscription"),
    path("inscription/mot-de-passe/", views_parents.inscription_mot_de_passe, name="inscription_mot_de_passe"),
    path("parents/", views_parents.parent_espace, name="parent_espace"),
    path("parents/enfants/<int:pk>/", views_parents.parent_espace, name="parent_enfant"),
    path("parents/notifications/", views_parents.parent_notifications, name="parent_notifications"),
    path("parents/annonces/", views_parents.parent_annonces, name="parent_annonces"),
    path("parents/bulletins/<int:pk>/", views_parents.parent_bulletin, name="parent_bulletin"),
    path("parents/bulletins/<int:pk>/<str:format>/", views_parents.parent_bulletin_fichier, name="parent_bulletin_fichier"),
    path("gestion/", include(gestion)),
]
