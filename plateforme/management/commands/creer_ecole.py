# python manage.py creer_ecole <adresse> "<nom>" --ville "Jacmel" --telephone "3712 3456" --prenom Marie --nom Joseph
# Même chose que « Nouvelle école » sur la plateforme, en ligne de commande.
#
# python manage.py creer_ecole nenuphars "Institution Les Nénuphars" --ville "Les Cayes" --sans-compte
# Base vide, sans compte : pour y restaurer la sauvegarde d'une école qui utilisait déjà
# le site seule (voir docs/plusieurs-ecoles.md).
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from core.telephone import normaliser_telephone
from plateforme.creation import CreationImpossible, creer_ecole
from plateforme.models import Ecole


class Command(BaseCommand):
    help = "Ouvre une nouvelle école : sa base de données et le compte de sa direction."

    def add_arguments(self, parser):
        parser.add_argument("adresse", help="Ex : stjoseph (pour stjoseph.votre-domaine.ht)")
        parser.add_argument("nom", help="Nom complet de l'école")
        parser.add_argument("--ville", required=True)
        parser.add_argument("--nom-court", default="")
        parser.add_argument("--telephone", help="Téléphone du (de la) responsable : son identifiant")
        parser.add_argument("--prenom", help="Prénom du (de la) responsable")
        parser.add_argument("--nom", dest="nom_responsable", help="Nom du (de la) responsable")
        parser.add_argument("--email", default="")
        parser.add_argument("--sans-compte", action="store_true",
                            help="Aucun compte : la base attend la restauration d'une sauvegarde")

    def handle(self, *args, **options):
        ecole = Ecole(sous_domaine=options["adresse"].strip().lower(), nom=options["nom"], ville=options["ville"],
                      nom_court=options["nom_court"])
        try:
            ecole.full_clean(exclude=["base"])
        except ValidationError as erreur:
            raise CommandError("; ".join(f"{c} : {' '.join(m)}" for c, m in erreur.message_dict.items()))
        if options["sans_compte"]:
            telephone = None
        else:
            if not (options["telephone"] and options["prenom"] and options["nom_responsable"]):
                raise CommandError("Indiquez --telephone, --prenom et --nom du (de la) responsable, ou --sans-compte.")
            telephone = normaliser_telephone(options["telephone"])
            if not telephone:
                raise CommandError("Numéro de téléphone incomplet.")
        try:
            ecole, compte, mot_de_passe = creer_ecole(
                ecole, options["prenom"], options["nom_responsable"], telephone, options["email"])
        except CreationImpossible as erreur:
            raise CommandError(str(erreur))
        self.stdout.write(self.style.SUCCESS(f"✓ {ecole.nom} est ouverte (base « {ecole.base} »)."))
        if compte is None:
            self.stdout.write(f"  Aucun compte. Restaurez maintenant la sauvegarde : "
                              f"python manage.py ecole {ecole.sous_domaine} restaurer_sauvegarde <fichier.zip>")
            return
        self.stdout.write(f"  Identifiant de la direction : {compte.username}")
        self.stdout.write(f"  Mot de passe provisoire     : {mot_de_passe}  (à changer à la première connexion)")
