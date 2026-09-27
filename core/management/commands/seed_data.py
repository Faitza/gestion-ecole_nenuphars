# core/management/commands/seed_data.py
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from datetime import timedelta

from django.utils import timezone

from core.models import (Section, Classe, Eleve, Professeur, Employe, Paiement, Note, Creneau, Cours,
                         Preinscription, MessageContact, Annonce, Absence, Incident, Bulletin)
from core import bulletins, choices, parents, professeurs

Utilisateur = get_user_model()


class Command(BaseCommand):
    help = "Crée le compte admin par défaut et quelques données d'exemple pour tester l'application"

    def handle(self, *args, **options):
        # Le compte admin/admin123 est pour les essais seulement, jamais en production
        if not settings.DEBUG:
            raise CommandError("seed_data sert aux essais : lancez-le seulement avec DJANGO_DEBUG=1.")

        # 1) Compte admin par défaut
        if not Utilisateur.objects.filter(username="admin").exists():
            Utilisateur.objects.create_superuser("admin", "admin@nenuphars.ht", "admin123")
            self.stdout.write(self.style.SUCCESS("✓ Compte admin créé (admin / admin123)"))
        else:
            self.stdout.write("• Compte admin existe déjà")

        # 2) Toutes les classes, de la 1ère année Kindergarten à la NS4
        sections = {s.nom: s for s in Section.objects.all()}
        classes = {}
        for nom, cycle in choices.CLASSES_PAR_DEFAUT:
            section = sections.get(choices.SECTION_PAR_CLASSE.get(nom))
            c, _ = Classe.objects.get_or_create(
                nom=nom, defaults=dict(cycle=cycle, section=section, annee_scolaire="2026-2027"),
            )
            classes[nom] = c
        self.stdout.write(self.style.SUCCESS(f"✓ {len(choices.CLASSES_PAR_DEFAUT)} classes créées (Kinder 1 → NS4)"))

        # Dates d'exemple proches d'aujourd'hui, pour voir les alertes d'anniversaire
        aujourd_hui = timezone.localdate()

        def il_y_a(annees, dans_jours=0):
            jour = aujourd_hui + timedelta(days=dans_jours)
            try:
                return jour.replace(year=jour.year - annees)
            except ValueError:  # 29 février
                return jour.replace(year=jour.year - annees, day=28)

        # 3) Professeurs
        # Emploi du temps de départ : un cours par classe, validé (jour, n° de l'heure de cours)
        professeurs_data = [
            ("Louis-Jean", "Phawens", "Informatique", [("7ème AF", 1, 0), ("8ème AF", 2, 1), ("9ème AF", 4, 3)],
             il_y_a(34), il_y_a(6, dans_jours=-40)),
            ("Toyo", "Daana Neissa", "ETAP", [("NSI", 1, 1), ("NSII", 3, 0), ("NSIII", 5, 2)],
             il_y_a(29, dans_jours=45), il_y_a(3, dans_jours=4)),
        ]
        heures = list(Creneau.objects.filter(section=sections.get(choices.SECTION_SECONDAIRE), est_un_cours=True))
        profs = {}
        for nom, prenom, matiere, cours, naissance, embauche in professeurs_data:
            p, _ = Professeur.objects.get_or_create(
                nom=nom, prenom=prenom,
                defaults=dict(matiere_principale=matiere, section=sections.get(choices.SECTION_SECONDAIRE),
                              date_naissance=naissance, date_embauche=embauche),
            )
            profs[nom] = p
            for classe_nom, jour, heure in cours if heures else []:
                Cours.objects.get_or_create(
                    professeur=p, classe=classes[classe_nom], jour=jour, creneau=heures[heure],
                    annee_scolaire=choices.annee_scolaire_courante(),
                    defaults=dict(matiere=matiere, statut=choices.STATUT_COURS_VALIDE),
                )
            professeurs.synchroniser_classes(p)
        self.stdout.write(self.style.SUCCESS(f"✓ {len(professeurs_data)} professeurs créés"))

        # Compte d'essai d'un professeur, pour la saisie des notes (prof / prof123)
        prof = profs["Louis-Jean"]
        if prof.utilisateur is None and not Utilisateur.objects.filter(username="prof").exists():
            prof.utilisateur = Utilisateur.objects.create_user("prof", password="prof123", first_name=prof.prenom,
                                                               last_name=prof.nom)
            prof.save()
            self.stdout.write(self.style.SUCCESS("✓ Compte professeur créé (prof / prof123)"))

        # 4) Employés
        employes_data = [
            ("Jean", "Marie", "Secrétaire", il_y_a(41, dans_jours=3), il_y_a(8, dans_jours=-100)),
            ("Pierre", "Claude", "Comptable", il_y_a(38, dans_jours=-60), il_y_a(10, dans_jours=6)),
        ]
        for nom, prenom, poste, naissance, embauche in employes_data:
            Employe.objects.get_or_create(nom=nom, prenom=prenom, defaults=dict(
                poste=poste, date_naissance=naissance, date_embauche=embauche,
            ))
        self.stdout.write(self.style.SUCCESS(f"✓ {len(employes_data)} employés créés"))

        # Compte d'essai de la secrétaire (secretaire / secretaire123) : son rôle suit son poste
        secretaire = Employe.objects.get(nom="Jean", prenom="Marie")
        if secretaire.utilisateur is None and not Utilisateur.objects.filter(username="secretaire").exists():
            secretaire.utilisateur = Utilisateur.objects.create_user(
                "secretaire", password="secretaire123", first_name=secretaire.prenom, last_name=secretaire.nom,
            )
            secretaire.save()
            self.stdout.write(self.style.SUCCESS("✓ Compte secrétaire créé (secretaire / secretaire123)"))

        # Compte d'essai de la direction du primaire (direction / direction123), pour accepter les préinscriptions
        directrice, _ = Employe.objects.get_or_create(nom="Célestin", prenom="Rose", defaults=dict(
            poste=choices.POSTES_DIRECTION_SECTION[1], section=sections.get(choices.SECTION_PRIMAIRE),
        ))
        if directrice.utilisateur is None and not Utilisateur.objects.filter(username="direction").exists():
            directrice.utilisateur = Utilisateur.objects.create_user(
                "direction", password="direction123", first_name=directrice.prenom, last_name=directrice.nom,
            )
            directrice.save()
            self.stdout.write(self.style.SUCCESS("✓ Compte direction du primaire créé (direction / direction123)"))

        # 5) Élèves
        eleves_data = [
            ("Dupont", "Jean", "Masculin", "7ème AF", "Marie Dupont", "509-3456-7890"),
            ("Martin", "Marie", "Féminin", "8ème AF", "Paul Martin", "509-3456-7891"),
            ("Bernard", "Pierre", "Masculin", "NSI", "Sophie Bernard", "509-3456-7892"),
        ]
        eleves = {}
        for nom, prenom, genre, classe_nom, parent, tel in eleves_data:
            e, _ = Eleve.objects.get_or_create(
                nom=nom, prenom=prenom,
                defaults=dict(genre=genre, classe=classes[classe_nom], nom_parent_tuteur=parent, telephone_parent=tel),
            )
            eleves[nom] = e
        self.stdout.write(self.style.SUCCESS(f"✓ {len(eleves_data)} élèves créés"))

        # 6) Notes
        # Saisies par les professeurs de ces matières
        notes_data = [
            ("Dupont", "Informatique", 85.0, "1er Trimestre", "Louis-Jean"),
            ("Martin", "Informatique", 78.0, "1er Trimestre", "Louis-Jean"),
            ("Bernard", "ETAP", 90.0, "1er Trimestre", "Toyo"),
        ]
        for nom_eleve, matiere, note_val, periode, nom_prof in notes_data:
            Note.objects.get_or_create(
                eleve=eleves[nom_eleve], matiere=matiere,
                defaults=dict(note=note_val, periode=periode, annee_scolaire=choices.annee_scolaire_courante(),
                              professeur=profs[nom_prof]),
            )
        self.stdout.write(self.style.SUCCESS(f"✓ {len(notes_data)} notes créées"))

        # 7) Paiements
        paiements_data = [
            ("Dupont", 5000, "Frais de Scolarité (mensualité)", "Espèces"),
            ("Martin", 5000, "Frais de Scolarité (mensualité)", "Mobile Money (MonCash/NatCash)"),
        ]
        for nom_eleve, montant, type_p, methode in paiements_data:
            Paiement.objects.get_or_create(
                eleve=eleves[nom_eleve], montant=montant, type_paiement=type_p,
                defaults=dict(methode_paiement=methode, statut="Payé"),
            )
        self.stdout.write(self.style.SUCCESS(f"✓ {len(paiements_data)} paiements créés"))

        # 8) Préinscriptions reçues par le site public, à différentes étapes, et un message de la page Contact
        preinscriptions_data = [
            ("Désir", "Kerline", "Féminin", il_y_a(9), "4ème AF", "Anne Désir", "3714 5566", choices.ETAPE_RECUE),
            ("Étienne", "Ruth", "Féminin", il_y_a(3), "1ère Année Kinder", "Paul Étienne", "3822 1144",
             choices.ETAPE_CHEZ_LA_DIRECTION),
            ("Noël", "Ricardo", "Masculin", il_y_a(8), "3ème AF", "Mireille Noël", "4611 2299", choices.ETAPE_CHEZ_LA_DIRECTION),
        ]
        for nom, prenom, genre, naissance, classe_nom, parent, tel, etape in preinscriptions_data:
            Preinscription.objects.get_or_create(nom=nom, prenom=prenom, defaults=dict(
                genre=genre, date_naissance=naissance, classe_demandee=classes[classe_nom], nom_parent=parent,
                telephone_parent=tel, adresse="Les Cayes", etape=etape,
            ))
        MessageContact.objects.get_or_create(nom="Marie-Claude Joseph", defaults=dict(
            telephone="3712 4455", message="Bonjour, quelle est la date de la réunion des parents ?",
        ))
        self.stdout.write(self.style.SUCCESS(f"✓ {len(preinscriptions_data)} préinscriptions et 1 message du site créés"))

        # 9) Familles : un compte parent déjà créé (Martin) et un code à remettre (Dupont)
        for eleve in eleves.values():
            parents.parent_de_l_eleve(eleve)
        famille = eleves["Martin"].parents.first()
        if famille.utilisateur is None and not Utilisateur.objects.filter(username="parent").exists():
            compte = Utilisateur.objects.create_user("parent", password="parent123", first_name="Paul", last_name="Martin")
            parents.relier(famille, compte)
            self.stdout.write(self.style.SUCCESS("✓ Compte parent créé (parent / parent123), enfant : Marie Martin"))
        famille = eleves["Dupont"].parents.first()
        if famille.code_acces:
            self.stdout.write(self.style.SUCCESS(
                f"✓ Code parent de Jean Dupont : {famille.code_acces} (téléphone {famille.telephone}), "
                "à essayer sur /inscription/"))

        # 10) Vie scolaire du secondaire : un surveillant, un censeur, une absence, un retard, un incident
        secondaire = sections.get(choices.SECTION_SECONDAIRE)
        comptes_vie = {}
        for identifiant, nom, prenom, poste in [("surveillant", "Wilner", "Jean", "Surveillant(e)"),
                                                ("censeur", "Mérisier", "Frantz", "Censeur")]:
            employe, _ = Employe.objects.get_or_create(nom=nom, prenom=prenom, defaults=dict(poste=poste, section=secondaire))
            if employe.utilisateur is None and not Utilisateur.objects.filter(username=identifiant).exists():
                employe.utilisateur = Utilisateur.objects.create_user(
                    identifiant, password=f"{identifiant}123", first_name=prenom, last_name=nom)
                employe.save()
                self.stdout.write(self.style.SUCCESS(f"✓ Compte {poste.lower()} du secondaire créé ({identifiant} / {identifiant}123)"))
            comptes_vie[identifiant] = employe.utilisateur
        aujourd_hui = timezone.localdate()
        Absence.objects.get_or_create(eleve=eleves["Martin"], date=aujourd_hui - timedelta(days=2), defaults=dict(
            type=choices.RETARD, minutes_retard=10, signalee_par=comptes_vie["surveillant"]))
        Absence.objects.get_or_create(eleve=eleves["Dupont"], date=aujourd_hui - timedelta(days=1), defaults=dict(
            type=choices.ABSENCE, justifiee=True, motif="Maladie", signalee_par=comptes_vie["surveillant"]))
        Incident.objects.get_or_create(eleve=eleves["Martin"], description="Téléphone utilisé en classe.", defaults=dict(
            date=aujourd_hui - timedelta(days=1), signale_par=comptes_vie["surveillant"], traite_par=comptes_vie["censeur"],
            statut=choices.INCIDENT_EN_COURS, sanction="Téléphone rendu aux parents"))
        Incident.objects.get_or_create(eleve=eleves["Bernard"], description="Bousculade à la récréation.", defaults=dict(
            signale_par=comptes_vie["surveillant"]))

        # 11) Annonces aux parents, et bulletins du 1er trimestre de la 8ème AF validés
        Annonce.objects.get_or_create(titre="Réunion des parents", defaults=dict(
            texte="Réunion de tous les parents le samedi 11 octobre à 9 h, dans la cour de l'école.",
            auteur=Utilisateur.objects.filter(username="secretaire").first()))
        Annonce.objects.get_or_create(titre="Examens du 1er trimestre", section=secondaire, defaults=dict(
            texte="Les examens du 1er trimestre du secondaire commencent le lundi 8 décembre."))
        huitieme, periode = classes["8ème AF"], choices.PERIODES[0]
        if not Bulletin.objects.filter(classe=huitieme, periode=periode, valide=True).exists():
            bulletins.enregistrer_remarques(huitieme, periode, choices.annee_scolaire_courante(), {
                eleves["Martin"].pk: {"conduite": "Bonne", "appreciation": "Bon début d'année, continuez."}})
            bulletins.valider(huitieme, periode, choices.annee_scolaire_courante(), par=None)
        self.stdout.write(self.style.SUCCESS("✓ Vie scolaire, 2 annonces et bulletins du 1er trimestre de la 8ème AF créés"))

        self.stdout.write(self.style.SUCCESS("\nBase de données remplie avec succès !"))
