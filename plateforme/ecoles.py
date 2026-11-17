# plateforme/ecoles.py
# Plusieurs écoles sur le même site : chaque école a sa propre base de données.
#
#   nenuphars.votre-domaine.ht  → base de l'école « nenuphars »
#   stjoseph.votre-domaine.ht   → base de l'école « stjoseph »
#   votre-domaine.ht            → la plateforme (liste des écoles, création d'une école)
#
# Le middleware (plateforme/middleware.py) reconnaît l'école à l'adresse, puis « l'active »
# pour la durée de la requête. Toutes les requêtes à la base partent alors vers la base de
# cette école (plateforme/routeur.py), les photos vont dans son dossier
# (plateforme/stockage.py) et la mémoire (cache) lui est propre. Les données d'une école ne
# peuvent donc pas apparaître chez une autre.
#
# Sans SAAS_DOMAINE (réglage), aucune école n'est activée : le site fonctionne comme avant,
# pour une seule école, avec la base « default » et les textes de site_public/contenu.py.
import copy
import re
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from django.conf import settings
from django.db import connections, transaction

_ecole_active = ContextVar("ecole_active", default=None)


class EcoleUnique:
    """L'école du site quand il n'y en a qu'une (mode sans SAAS_DOMAINE)."""
    base = "default"
    active = True
    sur_titre = "Institution"
    equipe = "l'équipe des Nénuphars"
    chez = "aux Nénuphars"

    @property
    def nom(self):
        from core import choices
        return choices.NOM_ECOLE

    @property
    def nom_court(self):
        from core import choices
        return choices.NOM_COURT_ECOLE

    nom_affiche = nom_court

    @property
    def ville(self):
        from core import choices
        return choices.VILLE_ECOLE

    @property
    def code(self):
        from core import choices
        return choices.CODE_ECOLE

    def contenu_site(self):
        from site_public import contenu
        return contenu


ECOLE_UNIQUE = EcoleUnique()


def mode_saas():
    return bool(getattr(settings, "SAAS_DOMAINE", ""))


def active():
    """L'école de la requête en cours (un objet Ecole), ou None."""
    return _ecole_active.get()


def courante():
    """L'école de la requête en cours, ou l'école unique du site : nom, nom_court, ville, code."""
    return _ecole_active.get() or ECOLE_UNIQUE


def alias():
    """Nom de la base de données à utiliser maintenant."""
    ecole = _ecole_active.get()
    return ecole.base if ecole is not None else "default"


def atomic(**options):
    """transaction.atomic() sur la base de l'école en cours.

    transaction.atomic() tout court protège la base « default » : avec plusieurs écoles,
    ce ne serait pas la bonne. Le code de l'école utilise donc toujours celle-ci."""
    return transaction.atomic(using=alias(), **options)


@contextmanager
def activer(ecole):
    """Toutes les requêtes à la base, à l'intérieur du bloc, vont vers l'école donnée."""
    if ecole is not None:
        enregistrer_base(ecole)
    jeton = _ecole_active.set(ecole)
    try:
        yield ecole
    finally:
        _ecole_active.reset(jeton)


# ─────────────────────────────────────────────────────────────
# Bases de données des écoles
# ─────────────────────────────────────────────────────────────
def nom_de_base(sous_domaine):
    """Nom de la base d'une nouvelle école : ecole_ suivi de l'adresse, sans tiret."""
    return "ecole_" + re.sub(r"[^a-z0-9]", "_", sous_domaine.lower())[:50]


def dossier_des_bases():
    dossier = Path(getattr(settings, "DOSSIER_BASES_ECOLES", settings.BASE_DIR / "bases_ecoles"))
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def reglages_de_base(base):
    """Les réglages de connexion d'une école : ceux de « default », avec un autre nom de base."""
    reglages = copy.deepcopy(connections.settings["default"])
    if reglages["ENGINE"].endswith("sqlite3"):
        reglages["NAME"] = str(dossier_des_bases() / f"{base}.sqlite3")
    else:
        reglages["NAME"] = base
    reglages["TEST"] = {**reglages.get("TEST", {}), "NAME": None}
    return reglages


def enregistrer_base(ecole):
    """Fait connaître la base de l'école à Django (une seule fois par processus)."""
    if ecole.base not in connections.settings:
        connections.settings[ecole.base] = reglages_de_base(ecole.base)
    return ecole.base


def creer_base(ecole):
    """Crée la base vide de l'école (le fichier SQLite est créé tout seul à la première requête)."""
    moteur = connections.settings["default"]["ENGINE"]
    if moteur.endswith("sqlite3"):
        return
    if not re.fullmatch(r"[a-z0-9_]+", ecole.base):
        raise ValueError(f"Nom de base refusé : {ecole.base}")
    with connections["default"].cursor() as curseur:
        if moteur.endswith("postgresql"):
            curseur.execute("SELECT 1 FROM pg_database WHERE datname = %s", [ecole.base])
            if curseur.fetchone() is None:
                curseur.execute(f'CREATE DATABASE "{ecole.base}"')
        else:
            curseur.execute(f"CREATE DATABASE IF NOT EXISTS `{ecole.base}` CHARACTER SET utf8mb4")


def migrer(ecole, verbosity=0, stdout=None):
    """Crée ou met à jour les tables de l'école (avec les sections et les rôles de départ)."""
    from django.core.management import call_command

    enregistrer_base(ecole)
    with activer(ecole):
        call_command("migrate", database=ecole.base, interactive=False, verbosity=verbosity,
                     **({"stdout": stdout} if stdout is not None else {}))


def ecole_par_adresse(hote):
    """L'école dont l'adresse est hote (sans le port), ou None. La plateforme renvoie None."""
    from .models import Ecole

    hote = (hote or "").split(":")[0].lower().rstrip(".")
    domaine = settings.SAAS_DOMAINE
    if not hote.endswith("." + domaine):
        return None
    sous_domaine = hote[: -len(domaine) - 1]
    if not sous_domaine or "." in sous_domaine:
        return None
    return Ecole.objects.using("default").filter(sous_domaine=sous_domaine).first()


def est_la_plateforme(hote):
    hote = (hote or "").split(":")[0].lower().rstrip(".")
    return hote in (settings.SAAS_DOMAINE, "www." + settings.SAAS_DOMAINE)


def cle_cache(cle, prefixe, version):
    """Clés de la mémoire (cache) propres à chaque école : compteurs, sections du site public..."""
    return f"{prefixe}:{version}:{alias()}:{cle}"
