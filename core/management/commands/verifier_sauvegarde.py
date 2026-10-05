# core/management/commands/verifier_sauvegarde.py
from django.core.management.base import BaseCommand, CommandError

from core import sauvegardes


class Command(BaseCommand):
    help = ("Restaure une sauvegarde dans une base vide, à part (rien n'est touché), "
            "et vérifie que toutes les lignes et toutes les photos reviennent.")

    def add_arguments(self, parser):
        parser.add_argument("fichier", nargs="?", help="Fichier .zip (par défaut : la dernière sauvegarde)")

    def handle(self, *args, **options):
        chemin = options["fichier"] or sauvegardes.derniere_sauvegarde()
        if not chemin:
            raise CommandError("Aucune sauvegarde trouvée. Lancez d'abord : python manage.py sauvegarder")
        self.stdout.write(f"Restauration d'essai de {chemin}...")
        problemes, contenu, lignes = sauvegardes.verifier(chemin)
        if problemes:
            for probleme in problemes:
                self.stderr.write(self.style.ERROR(f"✗ {probleme}"))
            raise CommandError("La sauvegarde ne se restaure pas entièrement.")
        principales = ["core.Eleve", "core.Classe", "core.Professeur", "core.Employe", "core.Paiement", "core.Note",
                       "core.Utilisateur"]
        detail = ", ".join(f"{t.split('.')[1]} {lignes.get(t, 0)}" for t in principales)
        self.stdout.write(self.style.SUCCESS(
            f"✓ Sauvegarde du {contenu['cree_le']} restaurée sans erreur : {sum(lignes.values())} lignes "
            f"({detail}) et {len(contenu['fichiers'])} fichiers."))
