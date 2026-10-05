# core/management/commands/sauvegarder.py
from django.core.management.base import BaseCommand

from core import sauvegardes


class Command(BaseCommand):
    help = "Sauvegarde toute l'école (base et photos) dans un fichier .zip, puis vérifie qu'il se restaure."

    def add_arguments(self, parser):
        parser.add_argument("--dossier", help="Dossier des sauvegardes (par défaut DJANGO_DOSSIER_SAUVEGARDES ou sauvegardes/)")
        parser.add_argument("--garder", type=int, default=30, help="Nombre de sauvegardes gardées (30 par défaut)")
        parser.add_argument("--sans-verification", action="store_true",
                            help="Ne pas restaurer la sauvegarde pour la vérifier (déconseillé)")

    def handle(self, *args, **options):
        chemin, contenu = sauvegardes.sauvegarder(options["dossier"])
        total = sum(contenu["lignes"].values())
        taille = chemin.stat().st_size / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(
            f"✓ Sauvegarde créée : {chemin} ({taille:.1f} Mo, {total} lignes, {len(contenu['fichiers'])} fichiers)"))
        if contenu["fichiers_deja_manquants"]:
            self.stdout.write(self.style.WARNING(
                f"• {len(contenu['fichiers_deja_manquants'])} photo(s) déjà absente(s) du disque avant la sauvegarde"))
        if not options["sans_verification"]:
            problemes, _, _ = sauvegardes.verifier(chemin)
            if problemes:
                for probleme in problemes:
                    self.stderr.write(self.style.ERROR(f"✗ {probleme}"))
                raise SystemExit(1)
            self.stdout.write(self.style.SUCCESS("✓ Vérifiée : elle se restaure entièrement"))
        for fichier in sauvegardes.supprimer_anciennes(options["garder"], options["dossier"]):
            self.stdout.write(f"• Ancienne sauvegarde effacée : {fichier.name}")
