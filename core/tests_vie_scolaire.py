# core/tests_vie_scolaire.py
# Vie scolaire (appel, incidents), bulletins trimestriels et annonces, et ce
# que les parents en voient.
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import anniversaires, bulletins, choices, parents
from .models import (Absence, Annonce, Appel, Bulletin, Classe, Eleve, Employe, Incident, Note, Parent, Professeur,
                     Section, Utilisateur)

MOT_DE_PASSE = "Nenuphar-Bleu-2026"
T1 = choices.PERIODES[0]


class AvecUneEcole(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.annee = choices.annee_scolaire_courante()
        cls.primaire = Section.objects.get(nom=choices.SECTION_PRIMAIRE)
        cls.secondaire = Section.objects.get(nom=choices.SECTION_SECONDAIRE)
        cls.sixieme = Classe.objects.create(nom="6ème AF", section=cls.primaire)
        cls.septieme = Classe.objects.create(nom="7ème AF", section=cls.secondaire)

        def eleve(nom, prenom, classe, telephone):
            return Eleve.objects.create(nom=nom, prenom=prenom, genre="Féminin", classe=classe,
                                        nom_parent_tuteur=f"Parent {nom}", telephone_parent=telephone)

        cls.naika = eleve("Joseph", "Naïka", cls.septieme, "3712 4455")
        cls.marc = eleve("Pierre", "Marc", cls.septieme, "3811 2233")
        cls.lucie = eleve("Alexis", "Lucie", cls.septieme, "3900 1122")
        cls.anne = eleve("Noël", "Anne", cls.sixieme, "3600 7788")

        def employe(identifiant, poste, section=None):
            compte = Utilisateur.objects.create_user(identifiant, password="x", first_name=identifiant.capitalize())
            Employe.objects.create(nom=identifiant, prenom="X", poste=poste, section=section, utilisateur=compte)
            return compte

        cls.surveillant = employe("surveillant", "Surveillant(e)", cls.secondaire)
        cls.censeur = employe("censeur", "Censeur", cls.secondaire)
        cls.dir_secondaire = employe("dirs", choices.POSTES_DIRECTION_SECTION[2], cls.secondaire)
        cls.dir_primaire = employe("dirp", choices.POSTES_DIRECTION_SECTION[1], cls.primaire)
        cls.secretaire = employe("sec", "Secrétaire")
        cls.prof = Utilisateur.objects.create_user("prof", password="x")
        professeur = Professeur.objects.create(nom="Dorsainvil", prenom="Jean", utilisateur=cls.prof)
        professeur.classes.add(cls.septieme)

        famille = parents.parent_de_l_eleve(cls.naika)
        cls.parent = parents.creer_compte(famille, MOT_DE_PASSE)
        cls.famille = famille
        parents.parent_de_l_eleve(cls.anne)  # une autre famille, au primaire

    def appel(self, classe, statuts, minutes=None):
        donnees = {f"e{e.pk}": s for e, s in statuts.items()}
        donnees.update({f"m{e.pk}": m for e, m in (minutes or {}).items()})
        return self.client.post(reverse("core:appel", args=[classe.pk]), donnees)


class AppelTests(AvecUneEcole):
    def test_le_surveillant_fait_l_appel_de_sa_section(self):
        self.client.force_login(self.surveillant)
        choix = self.client.get(reverse("core:appel_choix"))
        self.assertContains(choix, "7ème AF")
        self.assertNotContains(choix, "6ème AF")
        self.assertEqual(self.client.get(reverse("core:appel", args=[self.sixieme.pk])).status_code, 404)

        page = self.client.get(reverse("core:appel", args=[self.septieme.pk]))
        self.assertContains(page, "Joseph Naïka")
        reponse = self.appel(self.septieme, {self.naika: choices.RETARD, self.marc: choices.ABSENCE,
                                             self.lucie: choices.PRESENT}, minutes={self.naika: "25"})
        self.assertRedirects(reponse, reverse("core:appel_choix"))
        retard = Absence.objects.get(eleve=self.naika)
        self.assertEqual((retard.type, retard.minutes_retard, retard.signalee_par), (choices.RETARD, 25, self.surveillant))
        self.assertTrue(Absence.objects.filter(eleve=self.marc, type=choices.ABSENCE).exists())
        self.assertFalse(Absence.objects.filter(eleve=self.lucie).exists())
        self.assertTrue(Appel.objects.filter(classe=self.septieme, date=timezone.localdate()).exists())

        # Le censeur justifie ; refaire l'appel garde la justification, corriger « présent » l'efface
        absence = Absence.objects.get(eleve=self.marc)
        absence.justifiee, absence.motif = True, "Maladie"
        absence.save()
        self.appel(self.septieme, {self.naika: choices.PRESENT, self.marc: choices.ABSENCE})
        self.assertTrue(Absence.objects.get(eleve=self.marc).justifiee)
        self.assertFalse(Absence.objects.filter(eleve=self.naika).exists())
        self.assertEqual(Appel.objects.count(), 1)

    def test_le_professeur_fait_l_appel_de_ses_classes(self):
        self.client.force_login(self.prof)
        self.assertContains(self.client.get(reverse("core:appel_choix")), "7ème AF")
        self.appel(self.septieme, {self.lucie: choices.ABSENCE})
        self.assertTrue(Absence.objects.filter(eleve=self.lucie).exists())
        self.assertEqual(self.client.get(reverse("core:appel", args=[self.sixieme.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("core:vie_scolaire")).status_code, 403)

    def test_seuls_le_censeur_et_la_direction_justifient(self):
        absence = Absence.objects.create(eleve=self.marc, type=choices.ABSENCE)
        url = reverse("core:absence_justifier", args=[absence.pk])
        self.client.force_login(self.surveillant)
        self.assertEqual(self.client.post(url, {"justifiee": "oui"}).status_code, 403)
        self.client.force_login(self.dir_primaire)
        self.assertIn(self.client.post(url, {"justifiee": "oui"}).status_code, (403, 404))
        self.client.force_login(self.censeur)
        self.assertContains(self.client.get(reverse("core:vie_scolaire")), "Justifier")
        self.client.post(url, {"justifiee": "oui", "motif": "Rendez-vous médical"})
        absence.refresh_from_db()
        self.assertEqual((absence.justifiee, absence.motif), (True, "Rendez-vous médical"))

    def test_parent_et_secretaire_ne_font_pas_l_appel(self):
        for compte in (self.parent, self.secretaire):
            self.client.force_login(compte)
            self.assertEqual(self.client.get(reverse("core:appel", args=[self.septieme.pk])).status_code, 404)
            self.assertEqual(self.client.get(reverse("core:incident_nouveau")).status_code, 403)


class IncidentsTests(AvecUneEcole):
    def test_du_signalement_a_la_convocation(self):
        # 1. Un professeur signale ; il ne peut choisir que les élèves de ses classes
        self.client.force_login(self.prof)
        page = self.client.get(reverse("core:incident_nouveau"))
        self.assertContains(page, "Joseph Naïka")
        self.assertNotContains(page, "Noël Anne")
        self.client.post(reverse("core:incident_nouveau"), {
            "eleve": self.naika.pk, "date": timezone.localdate().isoformat(), "description": "Téléphone en classe."})
        incident = Incident.objects.get()
        self.assertEqual((incident.statut, incident.signale_par), (choices.INCIDENT_SIGNALE, self.prof))

        # 2. Pas encore traité : le parent ne le voit pas
        self.client.force_login(self.parent)
        self.assertNotContains(self.client.get(reverse("core:parent_espace")), "Téléphone en classe")

        # 3. Le censeur décide de la suite et convoque les parents
        self.client.force_login(self.censeur)
        self.assertContains(self.client.get(reverse("core:vie_scolaire")), "1</strong><span>incident à traiter")
        convocation = (timezone.localtime() + timedelta(days=2)).replace(hour=9, minute=0)
        self.client.post(reverse("core:incident_fiche", args=[incident.pk]), {
            "sanction": "Téléphone rendu aux parents", "statut": choices.INCIDENT_EN_COURS,
            "convocation_le": convocation.strftime("%Y-%m-%dT%H:%M")})
        incident.refresh_from_db()
        self.assertEqual((incident.statut, incident.traite_par), (choices.INCIDENT_EN_COURS, self.censeur))
        lettre = self.client.get(reverse("core:incident_convocation", args=[incident.pk]))
        self.assertContains(lettre, "Parent Joseph")
        self.assertContains(lettre, "9 h 00")

        # 4. Le parent voit l'incident, la suite et la convocation
        self.client.force_login(self.parent)
        espace = self.client.get(reverse("core:parent_espace"))
        self.assertContains(espace, "Téléphone en classe")
        self.assertContains(espace, "Téléphone rendu aux parents")
        self.assertContains(espace, "Vous êtes convoqué(e)")

    def test_le_surveillant_signale_mais_ne_sanctionne_pas(self):
        incident = Incident.objects.create(eleve=self.naika, description="Bousculade.")
        self.client.force_login(self.surveillant)
        page = self.client.get(reverse("core:incident_fiche", args=[incident.pk]))
        self.assertNotContains(page, "Suite donnée</h2>")
        self.client.post(reverse("core:incident_fiche", args=[incident.pk]), {"sanction": "Retenue", "statut": "Clos"})
        incident.refresh_from_db()
        self.assertEqual(incident.statut, choices.INCIDENT_SIGNALE)
        # Le censeur du secondaire ne voit pas les incidents du primaire
        autre = Incident.objects.create(eleve=self.anne, description="Retard répété.")
        self.client.force_login(self.censeur)
        self.assertEqual(self.client.get(reverse("core:incident_fiche", args=[autre.pk])).status_code, 404)


class BulletinsTests(AvecUneEcole):
    def noter(self, eleve, matiere, note, periode=T1):
        Note.objects.create(eleve=eleve, matiere=matiere, note=note, periode=periode, annee_scolaire=self.annee)

    def setUp(self):
        for eleve, maths, francais in [(self.naika, 80, 70), (self.marc, 60, 90), (self.lucie, 50, None)]:
            self.noter(eleve, "Mathématiques", maths)
            if francais is not None:
                self.noter(eleve, "Français", francais)
        debut, _ = choices.dates_du_trimestre(T1, self.annee)
        Absence.objects.create(eleve=self.naika, date=debut, type=choices.RETARD, minutes_retard=10)
        Absence.objects.create(eleve=self.naika, date=debut + timedelta(days=1), type=choices.ABSENCE)

    def test_moyenne_rang_absences(self):
        resultats = bulletins.calculer(self.septieme, T1, self.annee)
        naika, marc, lucie = (resultats[e.pk] for e in (self.naika, self.marc, self.lucie))
        self.assertEqual((naika["moyenne"], marc["moyenne"], lucie["moyenne"]), (Decimal("75.00"), Decimal("75.00"), Decimal("50.00")))
        self.assertEqual((naika["rang"], marc["rang"], lucie["rang"]), (1, 1, 3))  # égalité : même rang
        self.assertEqual((naika["absences"], naika["retards"]), (1, 1))
        francais = next(l for l in naika["lignes"] if l["matiere"] == "Français")
        self.assertEqual(Decimal(francais["moyenne_classe"]), Decimal("80.00"))
        self.assertEqual(bulletins.avancement(self.septieme, T1, self.annee)["etat"], bulletins.ETAT_INCOMPLET)
        self.noter(self.lucie, "Français", 65)
        self.assertEqual(bulletins.avancement(self.septieme, T1, self.annee)["etat"], bulletins.ETAT_A_VALIDER)

    def test_conduite_validation_et_parent(self):
        url = reverse("core:bulletins_classe", args=[self.septieme.pk])
        # Le censeur donne la conduite mais ne valide pas
        self.client.force_login(self.censeur)
        self.client.post(url, {"periode": T1, "action": "enregistrer", f"c{self.naika.pk}": "Très bonne"})
        self.assertEqual(Bulletin.objects.get(eleve=self.naika).conduite, "Très bonne")
        self.assertEqual(self.client.post(url, {"periode": T1, "action": "valider"}).status_code, 403)
        # La secrétaire lit et imprime, sans rien changer
        self.client.force_login(self.secretaire)
        self.assertContains(self.client.get(reverse("core:bulletins_imprimer", args=[self.septieme.pk])), "Aperçu")
        self.assertEqual(self.client.post(url, {"periode": T1, "action": "enregistrer"}).status_code, 403)
        # La direction du primaire ne voit pas le secondaire
        self.client.force_login(self.dir_primaire)
        self.assertEqual(self.client.get(url).status_code, 404)

        # Avant la validation, le parent ne voit rien
        self.client.force_login(self.parent)
        self.assertContains(self.client.get(reverse("core:parent_espace")), "En attente")
        bulletin = Bulletin.objects.get(eleve=self.naika)
        self.assertEqual(self.client.get(reverse("core:parent_bulletin", args=[bulletin.pk])).status_code, 404)

        # La direction du secondaire écrit son appréciation et valide
        self.client.force_login(self.dir_secondaire)
        self.client.post(url, {"periode": T1, "action": "valider", f"c{self.naika.pk}": "Très bonne",
                               f"a{self.naika.pk}": "Bon trimestre."})
        bulletin.refresh_from_db()
        self.assertTrue(bulletin.valide)
        self.assertEqual((bulletin.moyenne, bulletin.rang, bulletin.effectif), (Decimal("75.00"), 1, 3))
        self.assertEqual((bulletin.appreciation, bulletin.valide_par), ("Bon trimestre.", self.dir_secondaire))
        self.assertEqual(Bulletin.objects.filter(classe=self.septieme, valide=True).count(), 3)

        # Une fois publiés, plus rien ne change sans retirer la publication
        self.client.force_login(self.censeur)
        self.client.post(url, {"periode": T1, "action": "enregistrer", f"c{self.naika.pk}": "Passable"})
        self.assertEqual(Bulletin.objects.get(eleve=self.naika).conduite, "Très bonne")
        # Une note corrigée après la validation ne change pas le bulletin publié
        Note.objects.filter(eleve=self.naika, matiere="Mathématiques").update(note=20)
        self.client.force_login(self.parent)
        page = self.client.get(reverse("core:parent_bulletin", args=[bulletin.pk]))
        self.assertContains(page, "75 / 100")
        self.assertContains(page, "1er sur 3")
        self.assertContains(page, "Très bonne")
        self.assertContains(page, "Bon trimestre.")
        self.assertContains(self.client.get(reverse("core:parent_espace")), "Voir le bulletin")
        # Le bulletin d'un autre enfant reste invisible
        autre = Bulletin.objects.get(eleve=self.marc)
        self.assertEqual(self.client.get(reverse("core:parent_bulletin", args=[autre.pk])).status_code, 404)

        # Retirer la publication
        self.client.force_login(self.dir_secondaire)
        self.client.post(url, {"periode": T1, "action": "retirer"})
        self.client.force_login(self.parent)
        self.assertEqual(self.client.get(reverse("core:parent_bulletin", args=[bulletin.pk])).status_code, 404)

    def test_tableau_de_bord_de_la_direction(self):
        self.noter(self.lucie, "Français", 65)
        self.client.force_login(self.dir_secondaire)
        self.assertContains(self.client.get(reverse("core:dashboard")), "bulletins du 1er trimestre à valider"
                            if choices.trimestre_du_jour() == T1 else "Vie scolaire et bulletins")


class AnnoncesTests(AvecUneEcole):
    def test_qui_ecrit_a_qui(self):
        self.client.force_login(self.secretaire)
        self.client.post(reverse("core:annonce_creer"), {"pour": "ecole", "titre": "Réunion des parents",
                                                         "texte": "Samedi 11 octobre à 9 h."})
        self.client.force_login(self.dir_primaire)
        formulaire = self.client.get(reverse("core:annonce_creer"))
        self.assertNotContains(formulaire, "Tous les parents de l&#x27;école")
        self.assertNotContains(formulaire, "7ème AF")
        reponse = self.client.post(reverse("core:annonce_creer"), {"pour": f"classe-{self.septieme.pk}", "titre": "X",
                                                                   "texte": "Y"})
        self.assertEqual(reponse.status_code, 200)  # choix refusé
        self.client.post(reverse("core:annonce_creer"), {"pour": f"classe-{self.sixieme.pk}", "titre": "Sortie au musée",
                                                         "texte": "Jeudi, pour la 6ème AF."})
        reunion = Annonce.objects.get(titre="Réunion des parents")
        self.assertEqual(self.client.get(reverse("core:annonce_modifier", args=[reunion.pk])).status_code, 404)
        self.client.force_login(self.dir_secondaire)
        self.client.post(reverse("core:annonce_creer"), {"pour": f"section-{self.secondaire.pk}",
                                                         "titre": "Examens du secondaire", "texte": "Le 8 décembre."})

        # Le parent de Naïka (7ème AF, secondaire) voit l'école et le secondaire, pas la 6ème
        self.client.force_login(self.parent)
        self.assertEqual(parents.nouveautes(self.famille)["annonces"], 2)
        page = self.client.get(reverse("core:parent_annonces"))
        self.assertContains(page, "Réunion des parents")
        self.assertContains(page, "Examens du secondaire")
        self.assertNotContains(page, "Sortie au musée")
        self.assertContains(page, "Nouveau")
        self.assertEqual(parents.nouveautes(Parent.objects.get(pk=self.famille.pk))["annonces"], 0)

    def test_nouveautes_du_parent(self):
        Parent.objects.filter(pk=self.famille.pk).update(espace_vu_le=timezone.now(), annonces_vues_le=timezone.now())
        Annonce.objects.create(titre="Fête de l'école", texte="Le 18 mai.")
        Absence.objects.create(eleve=self.naika, type=choices.RETARD, minutes_retard=5)
        Incident.objects.create(eleve=self.naika, description="Bavardages.")  # pas encore traité : ne compte pas
        famille = Parent.objects.get(pk=self.famille.pk)
        nouveau = parents.nouveautes(famille)
        self.assertEqual((nouveau["annonces"], nouveau["absences"], nouveau["incidents"]), (1, 1, 0))
        self.assertIn("1 annonce et 1 absence ou retard", anniversaires.message_de_bienvenue(self.parent))

        self.client.force_login(self.parent)
        menu = self.client.get(reverse("core:parent_annonces"))
        self.assertContains(menu, '<span class="compteur" title="Nouveau depuis votre dernière visite">1</span>')
        espace = self.client.get(reverse("core:parent_espace"))
        self.assertContains(espace, "Retard de 5 min")
        self.assertNotContains(espace, "Bavardages")
        self.assertEqual(parents.nouveautes(Parent.objects.get(pk=self.famille.pk))["total"], 0)
