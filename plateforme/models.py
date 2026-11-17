# plateforme/models.py
# Le registre des écoles qui utilisent le site. Il vit seulement dans la base de la
# plateforme (« default ») ; chaque école a ensuite sa propre base, avec ses élèves,
# ses notes, ses paiements et ses comptes (voir plateforme/ecoles.py).
import re
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.db import models

# Adresses gardées pour la plateforme elle-même
SOUS_DOMAINES_RESERVES = {
    "www", "admin", "plateforme", "api", "mail", "smtp", "ftp", "static", "media", "app", "test", "demo",
}
FORMAT_SOUS_DOMAINE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")


def valider_sous_domaine(valeur):
    if not FORMAT_SOUS_DOMAINE.match(valeur or ""):
        raise ValidationError(
            "Seulement des lettres minuscules sans accent, des chiffres et des tirets (-), "
            "40 caractères au plus, sans tiret au début ni à la fin.")
    if valeur in SOUS_DOMAINES_RESERVES:
        raise ValidationError("Cette adresse est réservée à la plateforme. Choisissez-en une autre.")


class Ecole(models.Model):
    nom = models.CharField("nom complet", max_length=120, help_text="Ex : Collège Saint-Joseph")
    nom_court = models.CharField(
        "nom court", max_length=60, blank=True,
        help_text="Affiché en haut du site public. Ex : Saint-Joseph. Vide : le nom complet.")
    sous_domaine = models.CharField(
        "adresse du site", max_length=40, unique=True, validators=[valider_sous_domaine],
        help_text="Ex : stjoseph, pour stjoseph.votre-domaine.ht. À ne plus changer une fois donnée aux familles.")
    ville = models.CharField(max_length=80)
    # Nom de la base de données de l'école, choisi à la création et jamais changé
    base = models.CharField("base de données", max_length=63, unique=True, editable=False)
    active = models.BooleanField(
        default=True, help_text="Une école suspendue voit une page « Service suspendu » ; rien n'est effacé.")
    cree_le = models.DateTimeField("créée le", auto_now_add=True)

    # Coordonnées et présentation pour le site public de l'école
    adresse = models.CharField(max_length=200, blank=True)
    telephones = models.TextField("téléphones", blank=True, help_text="Un numéro par ligne.")
    whatsapp = models.CharField("WhatsApp", max_length=30, blank=True)
    courriel = models.EmailField(blank=True)
    accroche = models.CharField(
        max_length=120, blank=True,
        help_text="Grand titre de l'accueil, avant le nom de la ville. Ex : École du Kindergarten à la NSIV,")
    presentation = models.TextField("présentation", blank=True, help_text="Quelques phrases sur l'école.")

    class Meta:
        ordering = ["nom"]
        verbose_name = "école"

    def __str__(self):
        return self.nom

    @property
    def code(self):
        """Court et sans accent : préfixe des sauvegardes, dossier des photos."""
        return self.sous_domaine

    @property
    def nom_affiche(self):
        return self.nom_court or self.nom

    # Mots des pages communes à toutes les écoles (voir aussi ecoles.EcoleUnique)
    sur_titre = ""
    equipe = "l'équipe de l'école"
    chez = "dans notre école"

    def contenu_site(self):
        """Textes et coordonnées du site public, sur le modèle de site_public/contenu.py."""
        from site_public import contenu

        return SimpleNamespace(
            NOM=self.nom, VILLE=self.ville,
            ADRESSE=self.adresse or None,
            TELEPHONES=[t.strip() for t in self.telephones.splitlines() if t.strip()],
            WHATSAPP=self.whatsapp or None,
            COURRIEL=self.courriel or None,
            HORAIRES=[], FRAIS=[], DATES=[],
            PIECES_A_FOURNIR=contenu.PIECES_A_FOURNIR,
            ACCROCHE=(self.accroche or "École du Kindergarten à la NSIV,", f"{self.ville}."),
            PRESENTATION=self.presentation or (
                f"{self.nom} accueille les élèves à {self.ville}. Les parents suivent en ligne les notes, "
                "les absences et les bulletins de leurs enfants."),
            HISTOIRE=[], MOT_DE_LA_DIRECTRICE=[], VALEURS=[],
            MISE_A_JOUR_PAGES_LEGALES=contenu.MISE_A_JOUR_PAGES_LEGALES,
            CONSERVATION_PREINSCRIPTION=contenu.CONSERVATION_PREINSCRIPTION,
            CONSERVATION_DOSSIER_ELEVE=contenu.CONSERVATION_DOSSIER_ELEVE,
            SECTIONS=contenu.SECTIONS_GENERIQUES,
        )
