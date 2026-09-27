# core/tests_notifications.py
# Flèche de retour, bulletins à télécharger (PDF et image), « Informer les
# parents », élève malade et notifications des parents.
from datetime import timedelta

import pypdfium2
from django.urls import reverse
from django.utils import timezone

from . import anniversaires, bulletins, choices, notifications
from .models import AlerteSante, Bulletin, Incident, Note, Notification, Parent
from .tests_vie_scolaire import T1, AvecUneEcole


class FlecheDeRetourTests(AvecUneEcole):
    def test_sur_chaque_page_sauf_l_accueil(self):
        self.client.force_login(self.censeur)
        self.assertNotContains(self.client.get(reverse("core:dashboard")), 'id="fleche-retour"')
        self.assertContains(self.client.get(reverse("core:vie_scolaire")), 'id="fleche-retour"')
        incident = Incident.objects.create(eleve=self.naika, description="Bousculade.")
        # Sans page d'avant (lien ouvert directement), la flèche ramène au tableau de la vie scolaire
        self.assertContains(self.client.get(reverse("core:incident_fiche", args=[incident.pk])),
                            f'href="{reverse("core:vie_scolaire")}" class="fleche-retour"')
        self.client.force_login(self.parent)
        self.assertNotContains(self.client.get(reverse("core:parent_espace")), 'id="fleche-retour"')
        self.assertContains(self.client.get(reverse("core:parent_notifications")), 'id="fleche-retour"')


class TelechargementDesBulletinsTests(AvecUneEcole):
    def setUp(self):
        for eleve, note in [(self.naika, 80), (self.marc, 60)]:
            Note.objects.create(eleve=eleve, matiere="Mathématiques", note=note, periode=T1, annee_scolaire=self.annee)

    def test_l_ecole_telecharge_un_eleve_ou_toute_la_classe(self):
        self.client.force_login(self.secretaire)
        base = reverse("core:bulletin_eleve_fichier", args=[self.septieme.pk, self.naika.pk, "pdf"])
        pdf = self.client.get(f"{base}?periode={T1}")
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertIn('filename="bulletin-joseph-naika-1er-trimestre-', pdf["Content-Disposition"])
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        png = self.client.get(reverse("core:bulletin_eleve_fichier", args=[self.septieme.pk, self.naika.pk, "png"]))
        self.assertEqual(png["Content-Type"], "image/png")
        self.assertTrue(png.content.startswith(b"\x89PNG"))
        self.assertEqual(self.client.get(reverse("core:bulletin_eleve_fichier",
                                                 args=[self.septieme.pk, self.naika.pk, "doc"])).status_code, 404)
        classe = self.client.get(reverse("core:bulletins_classe_pdf", args=[self.septieme.pk]))
        self.assertTrue(classe.content.startswith(b"%PDF"))
        self.assertEqual(len(pypdfium2.PdfDocument(classe.content)), 3)  # une page par élève
        page = self.client.get(reverse("core:bulletin_eleve", args=[self.septieme.pk, self.naika.pk]))
        self.assertContains(page, "Télécharger en PDF")
        self.assertContains(page, "Télécharger en image (PNG)")
        # La direction du primaire ne télécharge pas les bulletins du secondaire
        self.client.force_login(self.dir_primaire)
        self.assertEqual(self.client.get(base).status_code, 404)

    def test_le_parent_telecharge_les_bulletins_valides_de_ses_enfants(self):
        bulletins.valider(self.septieme, T1, self.annee, self.dir_secondaire)
        sien, autre = Bulletin.objects.get(eleve=self.naika), Bulletin.objects.get(eleve=self.marc)
        self.client.force_login(self.parent)
        espace = self.client.get(reverse("core:parent_espace"))
        self.assertContains(espace, reverse("core:parent_bulletin_fichier", args=[sien.pk, "pdf"]))
        for format, debut in [("pdf", b"%PDF"), ("png", b"\x89PNG")]:
            reponse = self.client.get(reverse("core:parent_bulletin_fichier", args=[sien.pk, format]))
            self.assertTrue(reponse.content.startswith(debut))
            self.assertIn("attachment", reponse["Content-Disposition"])
        self.assertEqual(self.client.get(reverse("core:parent_bulletin_fichier", args=[autre.pk, "pdf"])).status_code, 404)
        bulletins.retirer(self.septieme, T1, self.annee)
        self.assertEqual(self.client.get(reverse("core:parent_bulletin_fichier", args=[sien.pk, "pdf"])).status_code, 404)


class InformerLesParentsTests(AvecUneEcole):
    def test_le_censeur_decide_d_informer_les_parents(self):
        incident = Incident.objects.create(eleve=self.naika, description="Bavardages répétés.", signale_par=self.surveillant)
        url = reverse("core:incident_fiche", args=[incident.pk])
        self.client.force_login(self.censeur)
        self.assertContains(self.client.get(url), "Informer les parents")
        self.client.post(url, {"sanction": "Avertissement", "statut": choices.INCIDENT_EN_COURS})
        self.assertFalse(Notification.objects.exists())
        self.client.force_login(self.parent)
        self.assertNotContains(self.client.get(reverse("core:parent_espace")), "Bavardages")

        self.client.force_login(self.censeur)
        self.client.post(url, {"sanction": "Avertissement", "statut": choices.INCIDENT_EN_COURS, "informer_parents": "on"})
        notification = Notification.objects.get()
        self.assertEqual((notification.parent, notification.categorie), (self.famille, choices.NOTIF_COMPORTEMENT))
        self.assertIn("Suite donnée : Avertissement", notification.texte)
        fiche = self.client.get(url)
        self.assertContains(fiche, "Parents informés : 1 compte parent a reçu une notification.")
        self.assertContains(fiche, "https://wa.me/50937124455?text=")

        self.client.force_login(self.parent)
        self.assertContains(self.client.get(reverse("core:parent_notifications")), "Comportement de Naïka à l&#x27;école")
        self.assertContains(self.client.get(reverse("core:parent_espace")), "Bavardages répétés.")

        # Le censeur change d'avis : la notification est retirée
        self.client.force_login(self.censeur)
        self.client.post(url, {"sanction": "Avertissement", "statut": choices.INCIDENT_CLOS})
        self.assertFalse(Notification.objects.exists())

    def test_une_convocation_informe_toujours_les_parents(self):
        incident = Incident.objects.create(eleve=self.naika, description="Bagarre.")
        convocation = (timezone.localtime() + timedelta(days=1)).replace(hour=10, minute=30)
        self.client.force_login(self.censeur)
        self.client.post(reverse("core:incident_fiche", args=[incident.pk]), {
            "sanction": "Exclusion d'un jour", "statut": choices.INCIDENT_EN_COURS,
            "convocation_le": convocation.strftime("%Y-%m-%dT%H:%M")})
        incident.refresh_from_db()
        self.assertTrue(incident.informer_parents)
        notification = Notification.objects.get()
        self.assertEqual(notification.categorie, choices.NOTIF_CONVOCATION)
        self.assertIn("à 10 h 30, au sujet de Naïka", notification.titre)


class EleveMaladeTests(AvecUneEcole):
    def test_le_surveillant_previent_les_parents(self):
        self.client.force_login(self.surveillant)
        self.assertContains(self.client.get(reverse("core:appel_choix")), "Élève malade")
        formulaire = self.client.get(reverse("core:sante_nouvelle"))
        self.assertContains(formulaire, "Joseph Naïka")
        self.assertNotContains(formulaire, "Noël Anne")  # pas de sa section
        reponse = self.client.post(reverse("core:sante_nouvelle"), {
            "eleve": self.naika.pk, "description": "Fièvre depuis la récréation.",
            "mesure": choices.MESURES_SANTE[1]})
        alerte = AlerteSante.objects.get()
        self.assertRedirects(reponse, reverse("core:sante_fiche", args=[alerte.pk]))
        fiche = self.client.get(reverse("core:sante_fiche", args=[alerte.pk]))
        self.assertContains(fiche, "1 compte parent a reçu une notification.")
        self.assertContains(fiche, "https://wa.me/50937124455?text=")
        self.assertContains(fiche, 'href="tel:3712')
        notification = Notification.objects.get()
        self.assertEqual((notification.categorie, notification.titre), (choices.NOTIF_SANTE, "Naïka est malade à l'école"))
        self.assertIn("Un parent doit venir à l'école", notification.texte)

        # Le censeur le voit dans la vie scolaire du jour
        self.client.force_login(self.censeur)
        self.assertContains(self.client.get(reverse("core:vie_scolaire")), "Fièvre depuis la récréation.")

        # Le parent a la notification, et la voit dans la partie « Santé » de son espace
        self.assertIn("Nouveau pour vous : 1 alerte santé.", anniversaires.message_de_bienvenue(self.parent))
        self.client.force_login(self.parent)
        espace = self.client.get(reverse("core:parent_espace"))
        self.assertContains(espace, "Malade à l'école : Fièvre depuis la récréation.")

    def test_qui_peut_signaler(self):
        alerte = AlerteSante.objects.create(eleve=self.anne, description="Mal de ventre.")
        self.client.force_login(self.secretaire)
        self.assertEqual(self.client.get(reverse("core:sante_nouvelle")).status_code, 403)
        self.client.force_login(self.surveillant)  # secondaire : ne voit pas une élève du primaire
        self.assertEqual(self.client.get(reverse("core:sante_fiche", args=[alerte.pk])).status_code, 404)
        self.client.force_login(self.parent)
        self.assertEqual(self.client.get(reverse("core:sante_nouvelle")).status_code, 403)


class NotificationsTests(AvecUneEcole):
    def test_appel_bulletin_et_page_des_notifications(self):
        self.client.force_login(self.surveillant)
        self.appel(self.septieme, {self.naika: choices.ABSENCE})
        notification = Notification.objects.get(parent=self.famille)
        self.assertEqual(notification.categorie, choices.NOTIF_ABSENCE)
        self.assertTrue(notification.titre.startswith("Naïka est absente le "))
        # L'appel est corrigé : Naïka était là, la notification disparaît
        self.appel(self.septieme, {self.naika: choices.PRESENT})
        self.assertFalse(Notification.objects.filter(parent=self.famille).exists())
        self.appel(self.septieme, {self.naika: choices.RETARD}, minutes={self.naika: "20"})
        self.assertIn("est arrivée en retard de 20 min", Notification.objects.get(parent=self.famille).titre)

        Note.objects.create(eleve=self.naika, matiere="Français", note=75, periode=T1, annee_scolaire=self.annee)
        bulletins.valider(self.septieme, T1, self.annee, self.dir_secondaire)
        self.assertEqual(Notification.objects.filter(parent=self.famille, categorie=choices.NOTIF_BULLETIN).count(), 1)

        self.client.force_login(self.parent)
        page = self.client.get(reverse("core:parent_notifications"))
        self.assertContains(page, "Nouvelles (2)")
        self.assertContains(page, "Le bulletin du 1er trimestre de Naïka est disponible")
        self.assertContains(page, reverse("core:parent_bulletin", args=[Bulletin.objects.get(eleve=self.naika).pk]))
        self.assertEqual(notifications.non_lues(self.famille).count(), 0)
        encore = self.client.get(reverse("core:parent_notifications"))  # plus rien de nouveau
        self.assertNotContains(encore, "Nouvelles (")
        self.assertContains(encore, "Le bulletin du 1er trimestre de Naïka est disponible")

        bulletins.retirer(self.septieme, T1, self.annee)
        self.assertFalse(Notification.objects.filter(categorie=choices.NOTIF_BULLETIN).exists())

    def test_la_notification_suit_ce_qui_change(self):
        absence = self.naika.absences.create(date=timezone.localdate(), type=choices.ABSENCE)
        notifications.pour_absence(absence)
        notifications.marquer_lues(self.famille)
        notifications.pour_absence(absence)  # rien n'a changé : reste lue
        self.assertEqual(notifications.non_lues(self.famille).count(), 0)
        absence.justifiee, absence.motif = True, "Maladie"
        absence.save()
        notifications.pour_absence(absence)  # justifiée : redevient nouvelle
        self.assertEqual(notifications.non_lues(self.famille).get().texte, "Justifiée : Maladie")
        self.assertEqual(Parent.objects.get(pk=self.famille.pk).notifications.count(), 1)
