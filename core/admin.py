# core/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (Utilisateur, Section, Classe, Eleve, Professeur, Employe, Paiement, Note, Creneau, Affectation, Cours,
                     Preinscription, MessageContact, Parent, Annonce, Appel, Absence, Incident, Bulletin, AlerteSante, Notification)


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "telephone", "email", "is_active")
    search_fields = ("username", "first_name", "last_name", "email", "telephone")
    fieldsets = UserAdmin.fieldsets + (
        ("École", {"fields": ("telephone", "doit_changer_mot_de_passe")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("École", {"fields": ("telephone", "doit_changer_mot_de_passe")}),
    )


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("nom", "ordre")


@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    list_display = ("nom", "section", "cycle", "annee_scolaire")
    list_filter = ("section", "cycle", "annee_scolaire")


@admin.register(Eleve)
class EleveAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "classe", "nom_parent_tuteur", "telephone_parent")
    list_filter = ("classe", "genre")
    search_fields = ("nom", "prenom", "email", "nom_parent_tuteur")


@admin.register(Professeur)
class ProfesseurAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "section", "matiere_principale", "date_naissance", "date_embauche", "utilisateur")
    list_filter = ("section", "matiere_principale")
    search_fields = ("nom", "prenom", "email")
    filter_horizontal = ("classes",)


@admin.register(Employe)
class EmployeAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "poste", "section", "date_naissance", "date_embauche", "utilisateur")
    list_filter = ("poste", "section")
    search_fields = ("nom", "prenom", "email")


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("eleve", "montant", "type_paiement", "methode_paiement", "statut", "date_paiement")
    list_filter = ("type_paiement", "methode_paiement", "statut")
    search_fields = ("eleve__nom", "eleve__prenom")


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    """Les notes se saisissent par les professeurs dans le site : ici, lecture seule."""
    list_display = ("eleve", "professeur", "matiere", "note", "periode", "annee_scolaire")
    list_filter = ("periode", "matiere", "annee_scolaire")
    search_fields = ("eleve__nom", "eleve__prenom", "matiere")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Creneau)
class CreneauAdmin(admin.ModelAdmin):
    list_display = ("nom", "section", "heure_debut", "heure_fin", "est_un_cours")
    list_filter = ("section",)


@admin.register(Affectation)
class AffectationAdmin(admin.ModelAdmin):
    list_display = ("professeur", "classe", "role", "date_debut", "date_fin")
    list_filter = ("classe__section", "role")


@admin.register(Cours)
class CoursAdmin(admin.ModelAdmin):
    list_display = ("professeur", "classe", "matiere", "jour", "creneau", "statut", "annee_scolaire")
    list_filter = ("statut", "jour", "classe", "annee_scolaire")


@admin.register(Preinscription)
class PreinscriptionAdmin(admin.ModelAdmin):
    list_display = ("numero", "nom", "prenom", "classe_demandee", "telephone_parent", "etape", "date_demande")
    list_filter = ("etape", "classe_demandee__section", "classe_demandee")
    search_fields = ("numero", "nom", "prenom", "nom_parent", "telephone_parent")
    readonly_fields = ("numero", "date_demande", "decision_par", "decision_le", "eleve")


@admin.register(MessageContact)
class MessageContactAdmin(admin.ModelAdmin):
    list_display = ("nom", "telephone", "email", "recu_le", "traite")
    list_filter = ("traite",)
    search_fields = ("nom", "telephone", "email", "message")


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ("nom", "telephone", "code_acces", "utilisateur", "compte_cree_le")
    search_fields = ("nom", "telephone", "enfants__nom", "enfants__prenom")
    filter_horizontal = ("enfants",)
    readonly_fields = ("code_acces", "code_cree_le", "compte_cree_le")


@admin.register(Annonce)
class AnnonceAdmin(admin.ModelAdmin):
    list_display = ("titre", "destinataires", "auteur", "publiee_le")
    list_filter = ("section",)
    search_fields = ("titre", "texte")


@admin.register(Appel)
class AppelAdmin(admin.ModelAdmin):
    list_display = ("classe", "date", "fait_par", "fait_le")
    list_filter = ("date", "classe")


@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ("eleve", "date", "type", "minutes_retard", "justifiee", "motif", "signalee_par")
    list_filter = ("type", "justifiee", "date")
    search_fields = ("eleve__nom", "eleve__prenom", "motif")


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("eleve", "date", "statut", "sanction", "informer_parents", "convocation_le", "signale_par",
                    "traite_par")
    list_filter = ("statut", "informer_parents", "date")
    search_fields = ("eleve__nom", "eleve__prenom", "description", "sanction")


@admin.register(Bulletin)
class BulletinAdmin(admin.ModelAdmin):
    list_display = ("eleve", "classe", "periode", "annee_scolaire", "moyenne", "rang", "conduite", "valide")
    list_filter = ("periode", "annee_scolaire", "valide", "classe")
    search_fields = ("eleve__nom", "eleve__prenom")
    readonly_fields = ("lignes", "moyenne", "rang", "effectif", "absences", "retards", "valide_par", "valide_le")


@admin.register(AlerteSante)
class AlerteSanteAdmin(admin.ModelAdmin):
    list_display = ("eleve", "cree_le", "mesure", "signale_par")
    list_filter = ("mesure",)
    search_fields = ("eleve__nom", "eleve__prenom", "description")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("parent", "categorie", "titre", "cree_le", "lue_le")
    list_filter = ("categorie",)
    search_fields = ("parent__nom", "titre")
