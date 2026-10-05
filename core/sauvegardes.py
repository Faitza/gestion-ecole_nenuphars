# core/sauvegardes.py
# Sauvegarde complète de l'école dans un seul fichier .zip :
#   donnees.json  → toute la base (élèves, notes, paiements, comptes...), lisible par
#                   n'importe quelle base (SQLite, PostgreSQL ou MySQL) ;
#   media/...     → les photos et pièces jointes ;
#   contenu.json  → date, nombre de lignes par table et liste des fichiers, pour vérifier.
# Une sauvegarde n'est utile que si elle se restaure : « verifier_sauvegarde » la
# restaure entièrement dans une base vide à part, puis compare tout.
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import django
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.utils import timezone

# Tables recréées toutes seules par « migrate », ou sans valeur à garder
EXCLUES = ["contenttypes", "auth.permission", "sessions", "admin.logentry"]
FORMAT_NOM = "nenuphars-%Y%m%d-%H%M%S.zip"


def dossier_des_sauvegardes():
    dossier = Path(getattr(settings, "DOSSIER_SAUVEGARDES", settings.BASE_DIR / "sauvegardes"))
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def modeles_sauvegardes():
    """Les modèles dont les lignes sont dans la sauvegarde."""
    exclues_app = {e for e in EXCLUES if "." not in e}
    exclus_modele = {e.lower() for e in EXCLUES if "." in e}
    return [m for m in apps.get_models()
            if m._meta.app_label not in exclues_app and m._meta.label_lower not in exclus_modele
            and m._meta.managed and not m._meta.proxy]


def compter(alias="default"):
    return {m._meta.label: m._default_manager.using(alias).count() for m in modeles_sauvegardes()}


def fichiers_references(alias="default"):
    """Tous les fichiers (photos, pièces) dont la base a besoin, relatifs à MEDIA_ROOT."""
    noms = set()
    for modele in modeles_sauvegardes():
        champs = [c.name for c in modele._meta.get_fields() if c.get_internal_type() in ("FileField", "ImageField")]
        for champ in champs:
            for nom in modele._default_manager.using(alias).exclude(**{champ: ""}).values_list(champ, flat=True):
                if nom:
                    noms.add(nom)
    return sorted(noms)


def sauvegarder(dossier=None):
    """Crée la sauvegarde et renvoie (chemin du .zip, contenu)."""
    dossier = Path(dossier) if dossier else dossier_des_sauvegardes()
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / timezone.localtime().strftime(FORMAT_NOM)
    media = Path(settings.MEDIA_ROOT)
    with tempfile.TemporaryDirectory() as temporaire:
        json_donnees = Path(temporaire) / "donnees.json"
        call_command("dumpdata", exclude=EXCLUES, natural_foreign=True, natural_primary=True,
                     output=str(json_donnees), verbosity=0)
        fichiers = fichiers_references()
        manquants = [f for f in fichiers if not (media / f).is_file()]
        contenu = {
            "cree_le": timezone.localtime().isoformat(timespec="seconds"),
            "django": django.get_version(),
            "base": connections["default"].vendor,
            "lignes": compter(),
            "fichiers": [f for f in fichiers if f not in manquants],
            "fichiers_deja_manquants": manquants,
        }
        with zipfile.ZipFile(chemin, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(json_donnees, "donnees.json")
            archive.writestr("contenu.json", json.dumps(contenu, ensure_ascii=False, indent=2))
            for nom in contenu["fichiers"]:
                # Les photos sont déjà en JPEG : inutile de les recompresser
                archive.write(media / nom, f"media/{nom}", compress_type=zipfile.ZIP_STORED)
    return chemin, contenu


def supprimer_anciennes(garder, dossier=None):
    """Garde les « garder » sauvegardes les plus récentes ; renvoie les fichiers effacés."""
    dossier = Path(dossier) if dossier else dossier_des_sauvegardes()
    toutes = sorted(dossier.glob("nenuphars-*.zip"))
    anciennes = toutes[:-garder] if garder > 0 else []
    for fichier in anciennes:
        fichier.unlink()
    return anciennes


def derniere_sauvegarde(dossier=None):
    dossier = Path(dossier) if dossier else dossier_des_sauvegardes()
    toutes = sorted(dossier.glob("nenuphars-*.zip"))
    return toutes[-1] if toutes else None


def restaurer_dans_la_base_du_site(chemin_zip, dossier_media):
    """Restaure la sauvegarde dans la base du site (tables créées, vidées puis remplies) et les
    fichiers dans dossier_media. Renvoie le contenu.json de la sauvegarde."""
    with zipfile.ZipFile(chemin_zip) as archive, tempfile.TemporaryDirectory() as temporaire:
        contenu = json.loads(archive.read("contenu.json"))
        archive.extract("donnees.json", temporaire)
        call_command("migrate", interactive=False, verbosity=0)
        # Les données de départ créées par les migrations (sections, rôles, horaires) sont
        # remplacées par celles de la sauvegarde.
        call_command("flush", interactive=False, verbosity=0)
        call_command("loaddata", str(Path(temporaire) / "donnees.json"), verbosity=0)
        dossier_media = Path(dossier_media)
        for nom in archive.namelist():
            if nom.startswith("media/") and not nom.endswith("/"):
                cible = (dossier_media / nom[len("media/"):]).resolve()
                # Jamais en dehors du dossier des photos, quel que soit le contenu du .zip
                if dossier_media.resolve() not in cible.parents:
                    raise ValueError(f"Chemin refusé dans la sauvegarde : {nom}")
                cible.parent.mkdir(parents=True, exist_ok=True)
                cible.write_bytes(archive.read(nom))
    return contenu


def etat_de_la_base(dossier_media):
    """Lignes par table et fichiers absents du disque : ce que la vérification compare."""
    return {
        "lignes": compter(),
        "fichiers_absents": [f for f in fichiers_references() if not (Path(dossier_media) / f).is_file()],
    }


def verifier(chemin_zip):
    """Restaure la sauvegarde dans une base SQLite neuve, à part, et compare tout.
    Renvoie (problèmes, contenu, lignes restaurées). Aucune donnée réelle n'est touchée :
    la restauration d'essai tourne dans un autre programme, réglé sur la base d'essai."""
    chemin_zip = Path(chemin_zip).resolve()
    with zipfile.ZipFile(chemin_zip) as archive:
        contenu = json.loads(archive.read("contenu.json"))
    with tempfile.TemporaryDirectory() as temporaire:
        rapport = Path(temporaire) / "rapport.json"
        env = {
            **os.environ,
            "DB_ENGINE": "sqlite", "DB_NAME": str(Path(temporaire) / "essai.sqlite3"),
            "DJANGO_MEDIA_ROOT": str(Path(temporaire) / "media"),
            "DJANGO_SECRET_KEY": settings.SECRET_KEY,
        }
        resultat = subprocess.run(
            [sys.executable, str(settings.BASE_DIR / "manage.py"), "restaurer_sauvegarde", str(chemin_zip),
             "--essai", str(rapport)],
            env=env, capture_output=True, text=True, timeout=30 * 60)
        if resultat.returncode != 0 or not rapport.exists():
            erreur = (resultat.stderr or resultat.stdout).strip().splitlines()
            return [f"La restauration d'essai a échoué : {erreur[-1] if erreur else 'erreur inconnue'}"], contenu, {}
        etat = json.loads(rapport.read_text(encoding="utf-8"))
    problemes = []
    for table, attendu in contenu["lignes"].items():
        trouve = etat["lignes"].get(table)
        if trouve != attendu:
            problemes.append(f"{table} : {attendu} lignes sauvegardées, {trouve} restaurées")
    deja_manquants = set(contenu.get("fichiers_deja_manquants", []))
    for nom in etat["fichiers_absents"]:
        if nom not in deja_manquants:
            problemes.append(f"Fichier manquant après restauration : {nom}")
    return problemes, contenu, etat["lignes"]
