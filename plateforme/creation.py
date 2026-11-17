# plateforme/creation.py
# Ouverture d'une nouvelle école : sa ligne dans le registre, sa base de données
# (tables, sections, rôles et horaires de départ) et le premier compte de sa direction.
import logging

from django.contrib.auth.models import Group

from core import roles
from core.models import Utilisateur
from core.professeurs import mot_de_passe_provisoire

from . import ecoles

journal = logging.getLogger("nenuphars")


class CreationImpossible(Exception):
    pass


def creer_ecole(ecole, prenom, nom, telephone, email=""):
    """ecole : une Ecole pas encore enregistrée. Renvoie (ecole, compte, mot de passe provisoire).

    Sans téléphone, la base reste sans aucun compte : c'est le cas d'une école qui
    utilisait déjà le site seule et dont on va restaurer la sauvegarde."""
    ecole.base = ecoles.nom_de_base(ecole.sous_domaine)
    ecole.save(using="default")
    try:
        ecoles.creer_base(ecole)
        ecoles.migrer(ecole)
        if not telephone:
            return ecole, None, None
        mot_de_passe = mot_de_passe_provisoire()
        with ecoles.activer(ecole), ecoles.atomic():
            compte = Utilisateur(
                username=telephone, first_name=prenom, last_name=nom, email=email or "", telephone=telephone,
                doit_changer_mot_de_passe=True)
            compte.set_password(mot_de_passe)
            compte.save()
            compte.groups.add(Group.objects.get(name=roles.DIRECTRICE_EN_CHEF))
    except Exception as erreur:
        journal.exception("Création de l'école %s impossible", ecole.sous_domaine)
        # Le registre ne garde pas une école à moitié créée ; sa base, s'il y en a une,
        # reste sur le serveur (rien n'est effacé automatiquement).
        ecole.delete(using="default")
        raise CreationImpossible(f"La création a échoué : {erreur}") from erreur
    return ecole, compte, mot_de_passe
