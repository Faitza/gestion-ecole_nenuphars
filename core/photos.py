# core/photos.py
# Photos des élèves, des professeurs et des employés. Elles sont réduites
# (800 px au plus, en JPEG) pour rester légères sur une connexion lente, et
# ne sont jamais servies directement : la vue core:photo vérifie d'abord que
# l'utilisateur connecté a le droit de voir la personne.
import uuid
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps

TAILLE_MAX = 5 * 1024 * 1024   # 5 Mo, comme dans le cahier des charges
COTE_MAX = 800


def chemin_photo(instance, nom_fichier):
    """Nom au hasard : l'adresse d'une photo ne dit rien sur la personne."""
    return f"photos/{instance._meta.model_name}/{uuid.uuid4().hex}.jpg"


def preparer(fichier):
    """Vérifie la taille, remet la photo dans le bon sens et la réduit. Renvoie un fichier JPEG."""
    if not isinstance(fichier, UploadedFile):
        return fichier  # photo déjà enregistrée, ou case « effacer » cochée
    if fichier.size > TAILLE_MAX:
        raise ValidationError("La photo est trop lourde (5 Mo au plus).")
    try:
        image = Image.open(fichier)
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (OSError, ValueError):
        raise ValidationError("Ce fichier n'est pas une photo lisible.")
    image.thumbnail((COTE_MAX, COTE_MAX))
    sortie = BytesIO()
    image.save(sortie, "JPEG", quality=85, optimize=True)
    return ContentFile(sortie.getvalue(), name="photo.jpg")


def supprimer_fichier(champ):
    """Efface le fichier d'une photo remplacée ou d'une fiche supprimée."""
    if champ and champ.name:
        champ.storage.delete(champ.name)
