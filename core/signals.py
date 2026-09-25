# core/signals.py
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Employe, Professeur
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
