# core/management/commands/seed_data.py
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from core.models import Section, Classe, Eleve, Professeur, Employe, Paiement, Note
from core import choices

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

        # 3) Professeurs
        professeurs_data = [
            ("Louis-Jean", "Phawens", "Informatique", ["7ème AF", "8ème AF", "9ème AF"]),
            ("Toyo", "Daana Neissa", "ETAP", ["NSI", "NSII", "NSIII"]),
        ]
        for nom, prenom, matiere, classes_noms in professeurs_data:
            p, _ = Professeur.objects.get_or_create(
                nom=nom, prenom=prenom,
                defaults=dict(matiere_principale=matiere, section=sections.get(choices.SECTION_SECONDAIRE)),
            )
            p.classes.set([classes[c] for c in classes_noms])
        self.stdout.write(self.style.SUCCESS(f"✓ {len(professeurs_data)} professeurs créés"))

        # 4) Employés
        employes_data = [
            ("Jean", "Marie", "Secrétaire"),
            ("Pierre", "Claude", "Comptable"),
        ]
        for nom, prenom, poste in employes_data:
            Employe.objects.get_or_create(nom=nom, prenom=prenom, defaults=dict(poste=poste))
        self.stdout.write(self.style.SUCCESS(f"✓ {len(employes_data)} employés créés"))

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
        notes_data = [
            ("Dupont", "Informatique", 85.0, "1er Trimestre"),
            ("Martin", "Informatique", 78.0, "1er Trimestre"),
            ("Bernard", "ETAP", 90.0, "1er Trimestre"),
        ]
        for nom_eleve, matiere, note_val, periode in notes_data:
            Note.objects.get_or_create(
                eleve=eleves[nom_eleve], matiere=matiere,
                defaults=dict(note=note_val, periode=periode, annee_scolaire="2026-2027"),
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

        self.stdout.write(self.style.SUCCESS("\n🎉 Base de données peuplée avec succès!"))
