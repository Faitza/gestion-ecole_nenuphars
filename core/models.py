# core/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from . import choices
from .telephone import normaliser_telephone


# ─────────────────────────────────────────────────────────────
# UTILISATEUR (un seul type de compte pour tout le monde ;
# le rôle vient des groupes, voir core/roles.py)
# ─────────────────────────────────────────────────────────────
class Utilisateur(AbstractUser):
    telephone = models.CharField(
        "téléphone", max_length=20, unique=True, null=True, blank=True,
        help_text="Peut servir d'identifiant de connexion. Ex : 3712 3456 ou +509 3712 3456.",
    )
    doit_changer_mot_de_passe = models.BooleanField(
        "doit changer son mot de passe", default=False,
        help_text="Coché à la création d'un compte avec un mot de passe provisoire.",
    )

    def clean(self):
        super().clean()
        # Avant le contrôle d'unicité des formulaires : « 3712 3456 » = « +509 3712-3456 »
        self.telephone = normaliser_telephone(self.telephone) or None

    def save(self, *args, **kwargs):
        # Même numéro, quelle que soit la façon de l'écrire (espaces, +509…)
        self.telephone = normaliser_telephone(self.telephone) or None
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
# SECTION (Kindergarten, Primaire, Secondaire) : organisation interne
# de l'école, chacune avec sa propre direction.
# ─────────────────────────────────────────────────────────────
class Section(models.Model):
    nom = models.CharField(max_length=50, unique=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordre", "nom"]

    def __str__(self):
        return self.nom


# ─────────────────────────────────────────────────────────────
# CLASSE (ex: 7ème AF, NSI...) — vraie table, éditable dans l'admin
# sans toucher au code, contrairement à une liste figée.
# ─────────────────────────────────────────────────────────────
class Classe(models.Model):
    nom = models.CharField(max_length=50, unique=True)             # ex: "7ème AF"
    cycle = models.CharField(max_length=20, choices=choices.CYCLES_CHOICES, blank=True)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="classes")
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
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="professeurs")
    utilisateur = models.OneToOneField(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True, related_name="professeur",
        help_text="Compte de connexion du professeur.",
    )
    date_embauche = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.nom} {self.prenom}"

    def save(self, *args, **kwargs):
        from .roles import synchroniser_role
        ancien = _ancien_utilisateur(self)
        super().save(*args, **kwargs)
        synchroniser_role(self, ancien)


# ─────────────────────────────────────────────────────────────
# EMPLOYÉ (personnel non-enseignant)
# ─────────────────────────────────────────────────────────────
class Employe(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    poste = models.CharField(max_length=100, choices=choices.POSTES_CHOICES, blank=True)
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True)
    section = models.ForeignKey(
        Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="employes",
        help_text="À remplir pour une direction de section, un(e) surveillant(e) ou un censeur.",
    )
    utilisateur = models.OneToOneField(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True, related_name="employe",
        help_text="Compte de connexion. Son rôle suit le poste.",
    )
    salaire = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    date_embauche = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.nom} {self.prenom}"

    def save(self, *args, **kwargs):
        from .roles import synchroniser_role
        ancien = _ancien_utilisateur(self)
        super().save(*args, **kwargs)
        synchroniser_role(self, ancien)


def _ancien_utilisateur(fiche):
    """Compte lié avant l'enregistrement, pour lui retirer le rôle s'il change."""
    if fiche.pk is None:
        return None
    ancien_id = type(fiche).objects.filter(pk=fiche.pk).values_list("utilisateur_id", flat=True).first()
    if ancien_id is None or ancien_id == fiche.utilisateur_id:
        return None
    return Utilisateur.objects.filter(pk=ancien_id).first()


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
