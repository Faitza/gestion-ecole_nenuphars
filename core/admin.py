# core/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur, Classe, Eleve, Professeur, Employe, Paiement, Note


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    pass


@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    list_display = ("nom", "cycle", "annee_scolaire")
    list_filter = ("cycle", "annee_scolaire")


@admin.register(Eleve)
class EleveAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "classe", "nom_parent_tuteur", "telephone_parent")
    list_filter = ("classe", "genre")
    search_fields = ("nom", "prenom", "email", "nom_parent_tuteur")


@admin.register(Professeur)
class ProfesseurAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "matiere_principale")
    list_filter = ("matiere_principale",)
    search_fields = ("nom", "prenom", "email")
    filter_horizontal = ("classes",)


@admin.register(Employe)
class EmployeAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "poste", "salaire")
    list_filter = ("poste",)
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
