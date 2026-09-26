# core/signals.py
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Eleve, Employe, Preinscription, Professeur
from .photos import supprimer_fichier
from . import roles


@receiver(post_delete, sender=Employe)
def employe_supprime(sender, instance, **kwargs):
    """Un employé retiré de la liste perd l'accès lié à son poste."""
    if instance.utilisateur_id:
        roles.retirer_roles(instance.utilisateur, roles.ROLES_DU_PERSONNEL)


@receiver(post_delete, sender=Professeur)
def professeur_supprime(sender, instance, **kwargs):
    if instance.utilisateur_id:
        roles.retirer_roles(instance.utilisateur, {roles.PROFESSEUR})


@receiver(post_delete, sender=Eleve)
@receiver(post_delete, sender=Employe)
@receiver(post_delete, sender=Professeur)
def photo_supprimee(sender, instance, **kwargs):
    """La photo d'une fiche supprimée (même par cascade) est effacée du disque."""
    if instance.photo:
        transaction.on_commit(lambda: supprimer_fichier(instance.photo))


@receiver(post_delete, sender=Preinscription)
def dossier_supprime(sender, instance, **kwargs):
    """Photo et pièces jointes d'une préinscription supprimée."""
    fichiers = [instance.photo, instance.acte_naissance, instance.dernier_bulletin]
    transaction.on_commit(lambda: [supprimer_fichier(champ) for champ in fichiers])
