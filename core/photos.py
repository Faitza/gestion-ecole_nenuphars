# core/photos.py
# Photos des élèves, des professeurs et des employés, et pièces jointes des
# préinscriptions (acte de naissance, bulletin). Les photos sont réduites
# (800 px au plus, en JPEG) pour rester légères sur une connexion lente. Rien
# n'est servi directement : les vues core:photo et core:piece vérifient
# d'abord que l'utilisateur connecté a le droit de voir la personne.
import uuid
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps

TAILLE_MAX = 5 * 1024 * 1024   # 5 Mo, comme dans le cahier des charges
COTE_MAX = 800
COTE_MAX_DOCUMENT = 1600   # un acte de naissance photographié doit rester lisible


def chemin_photo(instance, nom_fichier):
    """Nom au hasard : l'adresse d'une photo ne dit rien sur la personne."""
    return f"photos/{instance._meta.model_name}/{uuid.uuid4().hex}.jpg"


def chemin_piece(instance, nom_fichier):
    extension = ".pdf" if nom_fichier.lower().endswith(".pdf") else ".jpg"
    return f"pieces/{instance._meta.model_name}/{uuid.uuid4().hex}{extension}"


def _en_jpeg(fichier, cote_max, nom):
    """Photo remise dans le bon sens, réduite et réenregistrée en JPEG (sans les données EXIF)."""
    try:
        image = Image.open(fichier)
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (OSError, ValueError, Image.DecompressionBombError):
        raise ValidationError("Ce fichier n'est pas une photo lisible.")
    image.thumbnail((cote_max, cote_max))
    sortie = BytesIO()
    image.save(sortie, "JPEG", quality=85, optimize=True)
    return ContentFile(sortie.getvalue(), name=nom)


def preparer(fichier):
    """Vérifie la taille, remet la photo dans le bon sens et la réduit. Renvoie un fichier JPEG."""
    if not isinstance(fichier, UploadedFile):
        return fichier  # photo déjà enregistrée, ou case « effacer » cochée
    if fichier.size > TAILLE_MAX:
        raise ValidationError("La photo est trop lourde (5 Mo au plus).")
    return _en_jpeg(fichier, COTE_MAX, "photo.jpg")


def preparer_document(fichier):
    """Un PDF est gardé tel quel ; une photo du document est réduite en JPEG."""
    if not isinstance(fichier, UploadedFile):
        return fichier
    if fichier.size > TAILLE_MAX:
        raise ValidationError("Le fichier est trop lourd (5 Mo au plus).")
    debut = fichier.read(5)
    fichier.seek(0)
    if debut == b"%PDF-":
        return ContentFile(fichier.read(), name="document.pdf")
    try:
        return _en_jpeg(fichier, COTE_MAX_DOCUMENT, "document.jpg")
    except ValidationError:
        raise ValidationError("Envoyez un PDF ou une photo du document.")


def supprimer_fichier(champ):
    """Efface le fichier d'une photo remplacée ou d'une fiche supprimée."""
    if champ and champ.name:
        champ.storage.delete(champ.name)
