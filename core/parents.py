# core/parents.py
# Comptes parents (cahier des charges, section C). Il n'y a pas d'inscription
# libre : le secrétariat remet à chaque famille un code d'accès à usage
# unique (NEN-4K7P-29). Avec ce code et le téléphone donné à l'inscription,
# le parent crée son compte, qui est relié tout seul à ses enfants.
import re
import secrets

from django.contrib.auth.models import Group
from django.utils import timezone

from . import roles
from .models import Parent, Utilisateur
from .telephone import normaliser_telephone

PREFIXE = "NEN"
# Sans 0/O ni 1/I/L, pour qu'un code recopié à la main ne prête pas à confusion
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def nouveau_code():
    while True:
        brut = "".join(secrets.choice(_ALPHABET) for _ in range(6))
        code = f"{PREFIXE}-{brut[:4]}-{brut[4:]}"
        if not Parent.objects.filter(code_acces=code).exists():
            return code


def lire_code(texte):
    """« nen 4k7p 29 », « NEN-4K7P-29 » ou « 4K7P29 » donnent « NEN-4K7P-29 » (None si ce n'est pas un code)."""
    brut = re.sub(r"[^A-Za-z0-9]", "", texte or "").upper()
    if brut.startswith(PREFIXE):
        brut = brut[len(PREFIXE):]
    if len(brut) != 6:
        return None
    return f"{PREFIXE}-{brut[:4]}-{brut[4:]}"


def donner_un_code(parent):
    """Nouveau code pour une famille (un code perdu ne sert plus)."""
    parent.code_acces, parent.code_cree_le = nouveau_code(), timezone.now()
    parent.save(update_fields=["code_acces", "code_cree_le"])
    return parent.code_acces


def parent_de_l_eleve(eleve):
    """Trouve la famille de l'élève par son téléphone, ou la crée, et la relie à l'élève.

    Une famille qui n'a pas encore de compte reçoit un code. Renvoie None si
    la fiche de l'élève n'a pas de téléphone du parent.
    """
    numero = normaliser_telephone(eleve.telephone_parent)
    if len(numero) < 8:
        return None
    parent = Parent.objects.filter(telephone_normalise=numero).first()
    if parent is None:
        parent = Parent.objects.create(
            nom=(eleve.nom_parent_tuteur or f"Parent de {eleve.prenom} {eleve.nom}")[:150],
            telephone=eleve.telephone_parent[:30], email=eleve.email or "", adresse=(eleve.adresse or "")[:250],
        )
    parent.enfants.add(eleve)
    # Le téléphone de la fiche a changé : l'ancien code (pas encore utilisé) ne donne plus accès à l'élève
    for ancien in eleve.parents.filter(utilisateur__isnull=True).exclude(pk=parent.pk):
        ancien.enfants.remove(eleve)
        if not ancien.enfants.exists():
            ancien.delete()
    if parent.utilisateur_id is None and not parent.code_acces:
        donner_un_code(parent)
    return parent


def trouver(code, telephone):
    """La famille qui a ce code et ce téléphone, si le code n'a pas encore servi."""
    code, numero = lire_code(code), normaliser_telephone(telephone)
    if not code or len(numero) < 8:
        return None
    return Parent.objects.filter(code_acces=code, telephone_normalise=numero, utilisateur__isnull=True).first()


def compte_existant(parent):
    """Un compte a déjà ce téléphone (par exemple un professeur qui est aussi parent)."""
    return Utilisateur.objects.filter(telephone=parent.telephone_normalise, parent__isnull=True).first()


def creer_compte(parent, mot_de_passe):
    numero = parent.telephone_normalise
    identifiant = numero if not Utilisateur.objects.filter(username=numero).exists() else f"parent-{parent.pk}"
    prenom, _, nom = parent.nom.partition(" ")
    compte = Utilisateur.objects.create_user(
        username=identifiant, password=mot_de_passe, first_name=prenom[:150], last_name=nom[:150],
        telephone=None if Utilisateur.objects.filter(telephone=numero).exists() else numero,
        email=parent.email or "",
    )
    relier(parent, compte)
    return compte


def relier(parent, compte):
    """Le code a servi : il est effacé, et le compte reçoit le rôle Parent."""
    parent.utilisateur, parent.code_acces, parent.compte_cree_le = compte, None, timezone.now()
    parent.save(update_fields=["utilisateur", "code_acces", "compte_cree_le"])
    groupe, _ = Group.objects.get_or_create(name=roles.PARENT)
    compte.groups.add(groupe)
    compte.__dict__.pop("_roles_cache", None)


def peut_reinitialiser(compte):
    """Le secrétariat ne redonne un mot de passe qu'à un compte qui sert seulement de compte parent."""
    return not (compte.is_superuser or compte.is_staff) and roles.roles_de(compte) <= {roles.PARENT}


def codes_a_remettre():
    return Parent.objects.filter(utilisateur__isnull=True, code_acces__isnull=False)
