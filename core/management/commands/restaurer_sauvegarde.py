# core/management/commands/restaurer_sauvegarde.py
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import sauvegardes
from core.models import Eleve, Utilisateur


class Command(BaseCommand):
    help = ("Remet une sauvegarde dans la base du site (après une panne, ou chez un nouvel hébergeur). "
            "La base doit être neuve et vide : rien d'existant n'est effacé.")

    def add_arguments(self, parser):
        parser.add_argument("fichier", help="Fichier .zip créé par « python manage.py sauvegarder »")
        # Utilisé par « verifier_sauvegarde », sur une base d'essai : écrit le résultat dans ce fichier
        parser.add_argument("--essai", help="(interne) restauration d'essai, résultat écrit dans ce fichier JSON")

    def handle(self, *args, **options):
        # Sécurité : ne jamais écraser une école qui fonctionne
        try:
            deja_rempli = Utilisateur.objects.exists() or Eleve.objects.exists()
        except Exception:
            deja_rempli = False   # tables pas encore créées : base neuve
        if deja_rempli:
            raise CommandError(
                "La base du site contient déjà des comptes ou des élèves : rien n'a été restauré. "
                "Créez une base neuve et vide (voir docs/production.md), puis relancez.")

        if options["essai"]:
            sauvegardes.restaurer_dans_la_base_du_site(options["fichier"], settings.MEDIA_ROOT)
            etat = sauvegardes.etat_de_la_base(settings.MEDIA_ROOT)
            with open(options["essai"], "w", encoding="utf-8") as rapport:
                json.dump(etat, rapport)
            return

        # D'abord un essai à part : on ne commence pas une restauration qui échouerait à moitié
        problemes, contenu, _ = sauvegardes.verifier(options["fichier"])
        if problemes:
            for probleme in problemes:
                self.stderr.write(self.style.ERROR(f"✗ {probleme}"))
            raise CommandError("Cette sauvegarde ne se restaure pas entièrement : choisissez-en une autre.")
        sauvegardes.restaurer_dans_la_base_du_site(options["fichier"], settings.MEDIA_ROOT)
        self.stdout.write(self.style.SUCCESS(
            f"✓ Sauvegarde du {contenu['cree_le']} restaurée, avec {len(contenu['fichiers'])} fichiers. "
            "Les comptes et mots de passe sont ceux du jour de la sauvegarde."))
