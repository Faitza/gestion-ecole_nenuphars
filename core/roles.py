# core/roles.py
# Rôles (groupes Django) et droits d'accès, repris du tableau « Droits d'accès »
# du cahier des charges. Les rôles marqués « sa section » ne voient que les
# données de la section indiquée sur leur fiche employé.
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied

from . import choices

PARENT = "Parent"
PROFESSEUR = "Professeur"
SURVEILLANT = "Surveillant"
CENSEUR = "Censeur"
SECRETARIAT = "Secrétariat"
CAISSE = "Caisse"
DIRECTION_SECTION = "Direction de section"
DIRECTRICE_EN_CHEF = "Directrice en chef"

TOUS_LES_ROLES = [PARENT, PROFESSEUR, SURVEILLANT, CENSEUR, SECRETARIAT, CAISSE, DIRECTION_SECTION, DIRECTRICE_EN_CHEF]

# Rôles limités à leur section
ROLES_PAR_SECTION = {SURVEILLANT, CENSEUR, DIRECTION_SECTION}

# Rôle donné automatiquement au compte d'un employé selon son poste
ROLE_PAR_POSTE = {
    choices.POSTE_DIRECTION_GENERALE: DIRECTRICE_EN_CHEF,
    **{poste: DIRECTION_SECTION for poste in choices.POSTES_DIRECTION_SECTION},
    "Secrétaire": SECRETARIAT,
    "Comptable": CAISSE,
    "Caissier(ère)": CAISSE,
    "Surveillant(e)": SURVEILLANT,
    "Censeur": CENSEUR,
}
ROLES_DU_PERSONNEL = set(ROLE_PAR_POSTE.values())

# Module -> rôles qui peuvent lire / modifier (hors directrice en chef, qui a tout)
ACCES = {
    "eleves": {
        "lire": {SECRETARIAT, CAISSE, DIRECTION_SECTION, CENSEUR, SURVEILLANT},
        "ecrire": {SECRETARIAT},
    },
    "classes": {
        "lire": {SECRETARIAT, CAISSE, DIRECTION_SECTION, CENSEUR, SURVEILLANT},
        "ecrire": {SECRETARIAT},
    },
    "professeurs": {
        "lire": {SECRETARIAT, DIRECTION_SECTION, CENSEUR, SURVEILLANT},
        "ecrire": {SECRETARIAT},
    },
    "employes": {
        "lire": {CAISSE, DIRECTION_SECTION},
        "ecrire": set(),
    },
    "paiements": {
        "lire": {SECRETARIAT, CAISSE, DIRECTION_SECTION},
        "ecrire": {CAISSE},
    },
    "notes": {
        "lire": {SECRETARIAT, DIRECTION_SECTION},
        "ecrire": {DIRECTION_SECTION},
    },
    # Le secrétariat suit les demandes ; la direction de la section les voit
    # et décide (voir peut_decider_preinscription)
    "preinscriptions": {
        "lire": {SECRETARIAT, DIRECTION_SECTION},
        "ecrire": {SECRETARIAT},
    },
    # Messages envoyés depuis la page Contact du site public
    "messages_site": {
        "lire": {SECRETARIAT},
        "ecrire": {SECRETARIAT},
    },
}
MODULES = list(ACCES)

# Les notes sont saisies par les professeurs (page « Saisie des notes »). La
# direction d'une section peut les corriger ; la directrice en chef et le
# compte admin les lisent sans pouvoir en écrire.
LECTURE_SEULE_POUR_TOUT_VOIR = {"notes"}

# Chemin vers la section, pour filtrer chaque liste
CHEMIN_SECTION = {
    "eleves": "classe__section",
    "classes": "section",
    "professeurs": "section",
    "employes": "section",
    "paiements": "eleve__classe__section",
    "notes": "eleve__classe__section",
    "preinscriptions": "classe_demandee__section",
}


def roles_de(user):
    if not user.is_authenticated:
        return set()
    if not hasattr(user, "_roles_cache"):
        user._roles_cache = set(user.groups.values_list("name", flat=True))
    return user._roles_cache


def a_tout(user):
    return user.is_authenticated and (user.is_superuser or DIRECTRICE_EN_CHEF in roles_de(user))


def portee(user, module, ecriture=False):
    """« tout », « section » ou None (aucun accès)."""
    if a_tout(user):
        return None if ecriture and module in LECTURE_SEULE_POUR_TOUT_VOIR else "tout"
    autorises = roles_de(user) & ACCES[module]["ecrire" if ecriture else "lire"]
    if not autorises:
        return None
    return "section" if autorises <= ROLES_PAR_SECTION else "tout"


def peut(user, module, ecriture=False):
    return portee(user, module, ecriture) is not None


def voit_salaires(user):
    return a_tout(user) or CAISSE in roles_de(user)


def professeur_de(user):
    """Fiche professeur liée au compte, ou None."""
    return getattr(user, "professeur", None) if user.is_authenticated else None


def section_de(user):
    employe = getattr(user, "employe", None) if user.is_authenticated else None
    return employe.section if employe else None


def filtrer(user, module, queryset, ecriture=False, chemin=None):
    """Limite une liste à ce que l'utilisateur a le droit de voir (ou de modifier).

    `chemin` sert quand la liste n'est pas celle du module (ex. les élèves
    proposés dans le formulaire de notes : chemin="classe__section").
    """
    niveau = portee(user, module, ecriture)
    if niveau == "tout":
        return queryset
    section = section_de(user)
    chemin = chemin or CHEMIN_SECTION.get(module)
    if niveau == "section" and section is not None and chemin:
        return queryset.filter(**{chemin: section})
    return queryset.none()


def peut_valider_cours(user, section):
    """La direction d'une section valide les cours de sa section ; la directrice en chef, tous."""
    if a_tout(user):
        return True
    return DIRECTION_SECTION in roles_de(user) and section is not None and section_de(user) == section


def peut_decider_preinscription(user, preinscription):
    """La direction de la section demandée accepte ou refuse ; la directrice en chef aussi."""
    return peut_valider_cours(user, preinscription.section)


def acces_requis(module, ecriture=False):
    """Décorateur de vue : connexion obligatoire, puis 403 si le rôle n'a pas accès."""
    def decorateur(vue):
        @wraps(vue)
        @login_required
        def enveloppe(request, *args, **kwargs):
            if not peut(request.user, module, ecriture):
                raise PermissionDenied
            return vue(request, *args, **kwargs)
        return enveloppe
    return decorateur


def utilise_la_gestion(user):
    """Vrai si le compte a au moins un module de gestion (tableau de bord)."""
    return any(peut(user, module) for module in MODULES)


def synchroniser_role(fiche, ancien_utilisateur=None):
    """Donne au compte lié à une fiche Employe ou Professeur le rôle qui correspond.

    Pour un employé, le rôle suit le poste ; un compte détaché perd son rôle.
    """
    from .models import Professeur

    if isinstance(fiche, Professeur):
        noms_geres, nom_voulu = {PROFESSEUR}, PROFESSEUR
    else:
        noms_geres, nom_voulu = ROLES_DU_PERSONNEL, ROLE_PAR_POSTE.get(fiche.poste)

    if ancien_utilisateur is not None:
        retirer_roles(ancien_utilisateur, noms_geres)

    compte = fiche.utilisateur
    if compte is None:
        return
    retirer_roles(compte, noms_geres - {nom_voulu})
    if nom_voulu:
        groupe, _ = Group.objects.get_or_create(name=nom_voulu)
        compte.groups.add(groupe)
    compte.__dict__.pop("_roles_cache", None)


def retirer_roles(compte, noms):
    compte.groups.remove(*Group.objects.filter(name__in=noms))
    compte.__dict__.pop("_roles_cache", None)
