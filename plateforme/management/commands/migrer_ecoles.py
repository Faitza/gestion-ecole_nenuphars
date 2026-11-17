# python manage.py migrer_ecoles
# Après chaque mise à jour du site : crée ou met à jour les tables de la plateforme,
# puis celles de chaque école (à lancer à la place de « migrate »).
from django.core.management import call_command
from django.core.management.base import BaseCommand

from plateforme import ecoles
from plateforme.models import Ecole


class Command(BaseCommand):
    help = "Met à jour la base de la plateforme et celle de chaque école (après une mise à jour du site)."

    def handle(self, *args, **options):
        verbosity = options["verbosity"]
        self.stdout.write(self.style.MIGRATE_HEADING("── Plateforme (base « default »)"))
        call_command("migrate", interactive=False, verbosity=verbosity, stdout=self.stdout)
        for ecole in Ecole.objects.using("default").all():
            self.stdout.write(self.style.MIGRATE_HEADING(f"── {ecole.nom} ({ecole.sous_domaine})"))
            ecoles.migrer(ecole, verbosity=verbosity, stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("✓ Toutes les bases sont à jour."))
