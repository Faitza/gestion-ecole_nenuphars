# core/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from . import choices


# ─────────────────────────────────────────────────────────────
# UTILISATEUR (compte admin/staff — mot de passe géré par Django)
# ─────────────────────────────────────────────────────────────
class Utilisateur(AbstractUser):
    pass


# ─────────────────────────────────────────────────────────────
# CLASSE (ex: 7ème AF, NSI...) — vraie table, éditable dans l'admin
# sans toucher au code, contrairement à une liste figée.
# ─────────────────────────────────────────────────────────────
class Classe(models.Model):
    nom = models.CharField(max_length=50, unique=True)             # ex: "7ème AF"
    cycle = models.CharField(max_length=20, choices=choices.CYCLES_CHOICES, blank=True)
    annee_scolaire = models.CharField(max_length=20, blank=True)   # ex: "2026-2027"

    class Meta:
        ordering = ["cycle", "nom"]

    def __str__(self):
        return self.nom


# ─────────────────────────────────────────────────────────────
# ÉLÈVE
# ─────────────────────────────────────────────────────────────
class Eleve(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField(null=True, blank=True)
    genre = models.CharField(max_length=20, choices=choices.GENRES_CHOICES)
    classe = models.ForeignKey(Classe, on_delete=models.SET_NULL, null=True, blank=True, related_name="eleves")
    nom_parent_tuteur = models.CharField(max_length=150, blank=True)
    telephone_parent = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True, null=True)
    adresse = models.TextField(blank=True)
    date_inscription = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.nom} {self.prenom}"


# ─────────────────────────────────────────────────────────────
# PROFESSEUR
# ─────────────────────────────────────────────────────────────
class Professeur(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True)
    matiere_principale = models.CharField(max_length=100, choices=choices.MATIERES_CHOICES, blank=True)
    classes = models.ManyToManyField(Classe, blank=True, related_name="professeurs")
    date_embauche = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.nom} {self.prenom}"


# ─────────────────────────────────────────────────────────────
# EMPLOYÉ (personnel non-enseignant)
# ─────────────────────────────────────────────────────────────
class Employe(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    poste = models.CharField(max_length=100, choices=choices.POSTES_CHOICES, blank=True)
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True)
    salaire = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    date_embauche = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.nom} {self.prenom}"


# ─────────────────────────────────────────────────────────────
# PAIEMENT
# ─────────────────────────────────────────────────────────────
class Paiement(models.Model):
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="paiements")
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    type_paiement = models.CharField(max_length=50, choices=choices.TYPES_PAIEMENT_CHOICES)
    methode_paiement = models.CharField(max_length=50, choices=choices.METHODES_PAIEMENT_CHOICES)
    date_paiement = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=50, choices=choices.STATUTS_PAIEMENT_CHOICES, default="Payé")

    class Meta:
        ordering = ["-date_paiement"]

    def __str__(self):
        return f"{self.eleve} - {self.montant} HTG"


# ─────────────────────────────────────────────────────────────
# NOTE
# ─────────────────────────────────────────────────────────────
class Note(models.Model):
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="notes")
    professeur = models.ForeignKey(Professeur, on_delete=models.SET_NULL, null=True, blank=True, related_name="notes")
    matiere = models.CharField(max_length=100, choices=choices.MATIERES_CHOICES)
    note = models.DecimalField(max_digits=5, decimal_places=2)  # sur 100
    periode = models.CharField(max_length=20, choices=choices.PERIODES_CHOICES)
    annee_scolaire = models.CharField(max_length=20, blank=True)
    date_note = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_note"]

    def __str__(self):
        return f"{self.eleve} - {self.matiere} : {self.note}/100"
