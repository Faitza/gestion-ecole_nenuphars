# core/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur, Section, Classe, Eleve, Professeur, Employe, Paiement, Note


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
    list_display = ("nom", "prenom", "section", "matiere_principale", "utilisateur")
    list_filter = ("section", "matiere_principale")
    search_fields = ("nom", "prenom", "email")
    filter_horizontal = ("classes",)


@admin.register(Employe)
class EmployeAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "poste", "section", "utilisateur")
    list_filter = ("poste", "section")
    search_fields = ("nom", "prenom", "email")


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("eleve", "montant", "type_paiement", "methode_paiement", "statut", "date_paiement")
    list_filter = ("type_paiement", "methode_paiement", "statut")
    search_fields = ("eleve__nom", "eleve__prenom")


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("eleve", "professeur", "matiere", "note", "periode")
    list_filter = ("periode", "matiere")
    search_fields = ("eleve__nom", "eleve__prenom", "matiere")
