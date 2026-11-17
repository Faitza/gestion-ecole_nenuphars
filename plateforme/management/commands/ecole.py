# python manage.py ecole <adresse> <commande> [arguments...]
# python manage.py ecole --toutes <commande> [arguments...]
#
# Lance une commande habituelle pour une école de la plateforme, dans sa base et avec
# son dossier de photos. Exemples :
#   python manage.py ecole nenuphars sauvegarder
#   python manage.py ecole --toutes sauvegarder --garder 30
#   python manage.py ecole stjoseph seed_data
#   python manage.py ecole stjoseph createsuperuser
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from plateforme import ecoles
from plateforme.models import Ecole


class Command(BaseCommand):
    help = "Lance une commande pour une école (ou pour toutes), dans sa propre base de données."

    def add_arguments(self, parser):
        parser.add_argument("adresse", nargs="?", help="Adresse de l'école, ex : nenuphars")
        parser.add_argument("--toutes", action="store_true", help="Pour chaque école ouverte, l'une après l'autre")
        parser.add_argument("commande", nargs="...", help="La commande et ses arguments")

    def run_from_argv(self, argv):
        # « ecole --toutes sauvegarder --garder 30 » : tout ce qui suit la commande lui revient
        self._called_from_command_line = True
        reste = argv[2:]
        toutes = "--toutes" in reste[:1]
        if toutes:
            reste = reste[1:]
        if toutes and not reste or not toutes and len(reste) < 2:
            raise SystemExit("Usage : python manage.py ecole <adresse> <commande> [arguments]\n"
                             "        python manage.py ecole --toutes <commande> [arguments]")
        adresse = None if toutes else reste[0]
        commande = reste if toutes else reste[1:]
        try:
            self.lancer(adresse, toutes, commande)
        except CommandError as erreur:
            self.stderr.write(f"{erreur.__class__.__name__}: {erreur}")
            raise SystemExit(1)

    def handle(self, *args, **options):
        commande = options["commande"]
        if options["toutes"] and options["adresse"]:
            commande = [options["adresse"], *commande]
        self.lancer(None if options["toutes"] else options["adresse"], options["toutes"], commande)

    def lancer(self, adresse, toutes, commande):
        if not commande:
            raise CommandError("Indiquez la commande à lancer, ex : sauvegarder")
        if toutes:
            liste = list(Ecole.objects.using("default").filter(active=True))
        else:
            liste = list(Ecole.objects.using("default").filter(sous_domaine=adresse))
            if not liste:
                raise CommandError(f"Aucune école à l'adresse « {adresse} ».")
        echecs = []
        for ecole in liste:
            self.stdout.write(self.style.MIGRATE_HEADING(f"── {ecole.nom} ({ecole.sous_domaine})"))
            try:
                with ecoles.activer(ecole):
                    arguments = list(commande[1:])
                    # Les commandes de base de données travaillent sur la base de l'école
                    if commande[0] in ("migrate", "createsuperuser", "dumpdata", "loaddata", "flush", "dbshell",
                                       "changepassword") and not any(a.startswith("--database") for a in arguments):
                        arguments.append(f"--database={ecole.base}")
                    call_command(commande[0], *arguments)
            except (CommandError, SystemExit) as erreur:
                if not toutes:
                    raise CommandError(str(erreur) or "La commande a échoué.") from erreur
                echecs.append(ecole.sous_domaine)
                self.stderr.write(self.style.ERROR(f"✗ {ecole.sous_domaine} : {erreur}"))
        if echecs:
            raise CommandError(f"Échec pour : {', '.join(echecs)}")
