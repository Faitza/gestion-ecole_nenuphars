# core/models.py
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from . import choices
from .photos import chemin_photo, chemin_piece
from .telephone import normaliser_telephone


class AvecPhoto(models.Model):
    """Photo d'identité (élève, professeur, employé), demandée à l'inscription."""
    photo = models.ImageField(upload_to=chemin_photo, blank=True, help_text="Photo d'identité, 5 Mo au plus.")

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        ancienne = type(self).objects.filter(pk=self.pk).values_list("photo", flat=True).first() if self.pk else None
        super().save(*args, **kwargs)
        # Une photo remplacée ou retirée est effacée du disque (voir aussi core/signals.py)
        if ancienne and ancienne != self.photo.name:
            self.photo.storage.delete(ancienne)


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

    # Chaque section organise ses professeurs à sa façon (voir core/professeurs.py)
    @property
    def est_kindergarten(self):
        return self.nom == choices.SECTION_KINDERGARTEN

    @property
    def est_primaire(self):
        return self.nom == choices.SECTION_PRIMAIRE

    @property
    def est_secondaire(self):
        return self.nom == choices.SECTION_SECONDAIRE


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
class AgeEtAnciennete:
    """Âge et années à l'école, pour les fiches du personnel."""

    @property
    def age(self):
        from .anniversaires import age
        return age(self.date_naissance) if self.date_naissance else None

    @property
    def anciennete(self):
        """Années complètes passées à l'école."""
        from .anniversaires import age
        return age(self.date_embauche) if self.date_embauche else None


class Eleve(AvecPhoto):
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
class Professeur(AgeEtAnciennete, AvecPhoto):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True)
    date_naissance = models.DateField(null=True, blank=True)
    adresse = models.TextField(blank=True)
    diplome = models.CharField("diplôme", max_length=150, blank=True)
    matiere_principale = models.CharField(max_length=100, choices=choices.MATIERES_CHOICES, blank=True)
    # Rempli automatiquement à partir des affectations et des cours
    classes = models.ManyToManyField(Classe, blank=True, related_name="professeurs")
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="professeurs")
    utilisateur = models.OneToOneField(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True, related_name="professeur",
        help_text="Compte de connexion du professeur.",
    )
    date_embauche = models.DateField("date d'embauche", null=True, blank=True, help_text="Premier jour à l'école.")

    class Meta:
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.nom} {self.prenom}"

    def save(self, *args, **kwargs):
        from .roles import synchroniser_role
        ancien = _ancien_utilisateur(self)
        super().save(*args, **kwargs)
        synchroniser_role(self, ancien)

    @property
    def affectation_active(self):
        return self.affectations.filter(date_fin__isnull=True).select_related("classe").first()


# ─────────────────────────────────────────────────────────────
# EMPLOYÉ (personnel non-enseignant)
# ─────────────────────────────────────────────────────────────
class Employe(AgeEtAnciennete, AvecPhoto):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    poste = models.CharField(max_length=100, choices=choices.POSTES_CHOICES, blank=True)
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True)
    date_naissance = models.DateField("date de naissance", null=True, blank=True)
    adresse = models.TextField(blank=True)
    section = models.ForeignKey(
        Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="employes",
        help_text="À remplir pour une direction de section, un(e) surveillant(e) ou un censeur.",
    )
    utilisateur = models.OneToOneField(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True, related_name="employe",
        help_text="Compte de connexion. Son rôle suit le poste.",
    )
    salaire = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    date_embauche = models.DateField("date d'embauche", null=True, blank=True, help_text="Premier jour à l'école.")

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


# ─────────────────────────────────────────────────────────────
# EMPLOI DU TEMPS DES PROFESSEURS
# Kindergarten et primaire : le professeur est affecté à une classe
# pour toute la journée (Affectation). Secondaire : une ligne par cours
# (Cours), placée sur un créneau horaire de la section (Creneau).
# ─────────────────────────────────────────────────────────────
class Creneau(models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="creneaux")
    nom = models.CharField(max_length=50, help_text="Ex : 1re heure, Récréation")
    heure_debut = models.TimeField("début")
    heure_fin = models.TimeField("fin")
    est_un_cours = models.BooleanField("heure de cours", default=True, help_text="Décoché pour une récréation.")

    class Meta:
        ordering = ["section", "heure_debut"]
        verbose_name = "créneau"
        constraints = [
            models.UniqueConstraint(fields=["section", "heure_debut"], name="creneau_unique_par_section"),
        ]

    def __str__(self):
        return f"{self.nom} ({self.horaire})"

    @property
    def horaire(self):
        return f"{_heure(self.heure_debut)} – {_heure(self.heure_fin)}"

    @property
    def duree_minutes(self):
        return (self.heure_fin.hour * 60 + self.heure_fin.minute) - (self.heure_debut.hour * 60 + self.heure_debut.minute)


def _heure(t):
    return f"{t.hour} h {t.minute:02d}"


class Affectation(models.Model):
    professeur = models.ForeignKey(Professeur, on_delete=models.CASCADE, related_name="affectations")
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="affectations")
    role = models.CharField("rôle", max_length=30, choices=choices.ROLES_AFFECTATION_CHOICES, default=choices.ROLE_TITULAIRE)
    date_debut = models.DateField("début", default=timezone.localdate)
    date_fin = models.DateField("fin", null=True, blank=True, help_text="Vide tant que le professeur est dans la classe.")

    class Meta:
        ordering = ["-date_debut"]
        constraints = [
            # Une seule titulaire et une seule deuxième maîtresse par classe à la fois
            models.UniqueConstraint(
                fields=["classe", "role"], condition=Q(date_fin__isnull=True), name="affectation_un_role_par_classe",
            ),
            # Au Kindergarten et au primaire, un professeur n'a qu'une classe à la fois
            models.UniqueConstraint(
                fields=["professeur"], condition=Q(date_fin__isnull=True), name="affectation_une_classe_par_professeur",
            ),
        ]

    def __str__(self):
        return f"{self.professeur} – {self.classe} ({self.role})"


class Cours(models.Model):
    professeur = models.ForeignKey(Professeur, on_delete=models.CASCADE, related_name="cours")
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="cours")
    matiere = models.CharField("matière", max_length=100, choices=choices.MATIERES_CHOICES)
    jour = models.PositiveSmallIntegerField(choices=choices.JOURS_CHOICES)
    creneau = models.ForeignKey(Creneau, on_delete=models.PROTECT, related_name="cours", verbose_name="heure")
    statut = models.CharField(max_length=20, choices=choices.STATUTS_COURS_CHOICES, default=choices.STATUT_COURS_PROPOSE)
    annee_scolaire = models.CharField(max_length=20, default=choices.annee_scolaire_courante)

    class Meta:
        ordering = ["jour", "creneau__heure_debut"]
        verbose_name_plural = "cours"
        constraints = [
            models.UniqueConstraint(
                fields=["classe", "jour", "creneau", "annee_scolaire"], name="cours_une_classe_un_creneau",
            ),
            models.UniqueConstraint(
                fields=["professeur", "jour", "creneau", "annee_scolaire"], name="cours_un_professeur_un_creneau",
            ),
        ]

    def __str__(self):
        return f"{self.classe} · {self.matiere} · {self.get_jour_display()} {self.creneau.nom}"


# ─────────────────────────────────────────────────────────────
# PRÉINSCRIPTION (formulaire du site public). Le secrétariat vérifie le
# dossier, la direction de la section accepte ou refuse, puis le
# secrétariat inscrit l'élève, ce qui crée sa fiche Eleve.
# ─────────────────────────────────────────────────────────────
class Preinscription(AvecPhoto):
    numero = models.CharField("numéro de dossier", max_length=20, unique=True, null=True, blank=True, editable=False)
    # L'élève
    nom = models.CharField(max_length=100)
    prenom = models.CharField("prénom", max_length=100)
    date_naissance = models.DateField("date de naissance")
    genre = models.CharField(max_length=20, choices=choices.GENRES_CHOICES)
    classe_demandee = models.ForeignKey(
        Classe, on_delete=models.SET_NULL, null=True, verbose_name="classe demandée", related_name="preinscriptions",
    )
    ecole_precedente = models.CharField("école précédente", max_length=150, blank=True)
    # Le parent ou tuteur
    nom_parent = models.CharField("nom du parent ou tuteur", max_length=150)
    telephone_parent = models.CharField("téléphone", max_length=30)
    email_parent = models.EmailField("e-mail", blank=True)
    adresse = models.CharField(max_length=250, blank=True)
    # Pièces jointes, facultatives (PDF ou photo)
    acte_naissance = models.FileField("acte de naissance", upload_to=chemin_piece, blank=True)
    dernier_bulletin = models.FileField("dernier bulletin", upload_to=chemin_piece, blank=True)
    # Suivi par l'école
    etape = models.CharField("étape", max_length=30, choices=choices.ETAPES_PREINSCRIPTION_CHOICES, default=choices.ETAPE_RECUE)
    rendez_vous = models.DateTimeField("rendez-vous", null=True, blank=True, help_text="Rendez-vous avec la famille au secrétariat.")
    note_interne = models.TextField("note du secrétariat", blank=True, help_text="Visible seulement par le personnel.")
    avis_direction = models.TextField("avis de la direction", blank=True)
    decision_par = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    decision_le = models.DateTimeField(null=True, blank=True)
    eleve = models.OneToOneField(Eleve, on_delete=models.SET_NULL, null=True, blank=True, related_name="preinscription")
    date_demande = models.DateTimeField("reçue le", auto_now_add=True)
    mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_demande"]
        verbose_name = "préinscription"

    def __str__(self):
        return f"{self.numero or 'Préinscription'} · {self.nom} {self.prenom}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Numéro de dossier donné à la famille : PRE-2026-0147
        if not self.numero:
            self.numero = f"PRE-{self.date_demande.year}-{self.pk:04d}"
            type(self).objects.filter(pk=self.pk).update(numero=self.numero)

    @property
    def section(self):
        return self.classe_demandee.section if self.classe_demandee_id else None

    @property
    def en_cours(self):
        return self.etape in choices.ETAPES_EN_COURS

    @property
    def pieces(self):
        """[(nom du champ, libellé)] des pièces jointes envoyées."""
        return [(champ, type(self)._meta.get_field(champ).verbose_name)
                for champ in ("acte_naissance", "dernier_bulletin") if getattr(self, champ)]


# ─────────────────────────────────────────────────────────────
# MESSAGE envoyé depuis la page Contact du site public
# ─────────────────────────────────────────────────────────────
class MessageContact(models.Model):
    nom = models.CharField(max_length=150)
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    email = models.EmailField("e-mail", blank=True)
    message = models.TextField()
    recu_le = models.DateTimeField("reçu le", auto_now_add=True)
    traite = models.BooleanField("traité", default=False)
    traite_par = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    traite_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["traite", "-recu_le"]
        verbose_name = "message du site"
        verbose_name_plural = "messages du site"

    def __str__(self):
        return f"{self.nom} · {self.recu_le:%d/%m/%Y}"
