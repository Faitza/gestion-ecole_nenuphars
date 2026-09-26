# site_public/tests.py
# Site public, préinscription en ligne et suivi du dossier jusqu'à l'inscription.
import tempfile
from datetime import date
from io import BytesIO

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from core import choices, roles
from core.models import Classe, Eleve, Employe, MessageContact, Preinscription, Professeur, Section, Utilisateur


def image(largeur=2400, hauteur=1800, nom="photo.png"):
    tampon = BytesIO()
    Image.new("RGB", (largeur, hauteur), (30, 60, 140)).save(tampon, "PNG")
    return SimpleUploadedFile(nom, tampon.getvalue(), content_type="image/png")


def pdf(nom="acte.pdf"):
    return SimpleUploadedFile(nom, b"%PDF-1.4\n% essai\n%%EOF\n", content_type="application/pdf")


class AvecDossierTemporaire(TestCase):
    """Les photos et les pièces jointes des tests vont dans un dossier jetable."""

    def setUp(self):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        reglage = self.settings(MEDIA_ROOT=dossier.name)
        reglage.enable()
        self.addCleanup(reglage.disable)


class PagesPubliquesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        primaire = Section.objects.get(nom=choices.SECTION_PRIMAIRE)
        Classe.objects.create(nom="6ème AF", section=primaire)
        Classe.objects.create(nom="1ère AF", section=primaire)
        Employe.objects.create(nom="Delva", prenom="Nadia", poste=choices.POSTES_DIRECTION_SECTION[1], section=primaire)
        Employe.objects.create(nom="Pierre", prenom="Jean", poste="Comptable")

    def test_pages_ouvertes_sans_connexion(self):
        for nom, texte in [("accueil", "Préinscrire mon enfant"), ("ecole", "Une direction pour chaque section"),
                           ("niveaux", "Du Kindergarten au Nouveau Secondaire"), ("admissions", "Pièces à fournir"),
                           ("preinscription", "Envoyer la demande"), ("contact", "Écrire à l'école")]:
            with self.subTest(page=nom):
                self.assertContains(self.client.get(reverse(f"site:{nom}")), texte)

    def test_accueil_a_la_racine_et_gestion_a_part(self):
        self.assertEqual(reverse("site:accueil"), "/")
        self.assertEqual(reverse("core:dashboard"), "/gestion/")
        reponse = self.client.get("/")
        self.assertContains(reponse, "Se connecter")
        self.assertContains(reponse, f"Préinscriptions {choices.annee_scolaire_courante()} ouvertes")

    def test_niveaux_dans_l_ordre_et_equipe_de_direction(self):
        contenu = self.client.get(reverse("site:niveaux")).content.decode()
        self.assertLess(contenu.index("1ère AF"), contenu.index("6ème AF"))
        reponse = self.client.get(reverse("site:ecole"))
        self.assertContains(reponse, "Nadia Delva")
        self.assertNotContains(reponse, "Jean Pierre")  # seules les directions sont présentées

    def test_connecte_voit_mon_espace(self):
        self.client.force_login(Utilisateur.objects.create_user("x", password="x"))
        self.assertContains(self.client.get("/"), "Mon espace")


class PreinscriptionEnLigneTests(AvecDossierTemporaire):
    @classmethod
    def setUpTestData(cls):
        cls.primaire = Section.objects.get(nom=choices.SECTION_PRIMAIRE)
        cls.sixieme = Classe.objects.create(nom="6ème AF", section=cls.primaire)

    def donnees(self, **autres):
        return {
            "nom": "Joseph", "prenom": "Naïka", "date_naissance": "2015-03-14", "genre": "Féminin",
            "classe_demandee": self.sixieme.pk, "ecole_precedente": "École nationale de Torbeck",
            "nom_parent": "Marie-Claude Joseph", "telephone_parent": "3712 4455", "email_parent": "",
            "adresse": "Rue Geffrard, Les Cayes", **autres,
        }

    def test_demande_avec_photo_et_pieces(self):
        reponse = self.client.post(reverse("site:preinscription"), self.donnees(
            photo=image(), acte_naissance=pdf(), dernier_bulletin=image(3000, 2000, "bulletin.png")))
        self.assertRedirects(reponse, reverse("site:preinscription_envoyee"))
        dossier = Preinscription.objects.get()
        self.assertEqual(dossier.numero, f"PRE-{dossier.date_demande.year}-{dossier.pk:04d}")
        self.assertEqual(dossier.etape, choices.ETAPE_RECUE)
        self.assertRegex(dossier.photo.name, r"^photos/preinscription/[0-9a-f]{32}\.jpg$")
        self.assertRegex(dossier.acte_naissance.name, r"^pieces/preinscription/[0-9a-f]{32}\.pdf$")
        self.assertRegex(dossier.dernier_bulletin.name, r"^pieces/preinscription/[0-9a-f]{32}\.jpg$")
        with dossier.photo.open("rb") as f:
            self.assertEqual(max(Image.open(f).size), 800)
        with dossier.dernier_bulletin.open("rb") as f:
            self.assertEqual(max(Image.open(f).size), 1600)  # un document reste lisible

        # La famille voit son numéro de dossier ; un autre visiteur ne le voit pas
        self.assertContains(self.client.get(reverse("site:preinscription_envoyee")), dossier.numero)
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("site:preinscription_envoyee")), dossier.numero)

    def test_sans_pieces_jointes(self):
        self.client.post(reverse("site:preinscription"), self.donnees())
        dossier = Preinscription.objects.get()
        self.assertFalse(dossier.photo)
        self.assertEqual(dossier.pieces, [])

    def test_erreurs_rien_n_est_enregistre(self):
        cas = {
            "date dans le futur": {"date_naissance": "2030-01-01"},
            "numéro incomplet": {"telephone_parent": "3712"},
            "classe manquante": {"classe_demandee": ""},
            "fichier illisible": {"acte_naissance": SimpleUploadedFile("acte.txt", b"bonjour", content_type="text/plain")},
            "photo trop lourde": {"photo": SimpleUploadedFile("p.jpg", b"0" * (5 * 1024 * 1024 + 1), content_type="image/jpeg")},
        }
        for nom, champs in cas.items():
            with self.subTest(cas=nom):
                reponse = self.client.post(reverse("site:preinscription"), self.donnees(**champs))
                self.assertEqual(reponse.status_code, 200)
                self.assertContains(reponse, "à corriger")
        self.assertFalse(Preinscription.objects.exists())

    def test_robot_ignore(self):
        reponse = self.client.post(reverse("site:preinscription"), self.donnees(site_web="http://spam.example"))
        self.assertRedirects(reponse, reverse("site:preinscription_envoyee"))
        self.assertFalse(Preinscription.objects.exists())


class SuiviDesPreinscriptionsTests(AvecDossierTemporaire):
    """Secrétariat, direction de section et directrice en chef, du dossier à l'inscription."""

    @classmethod
    def setUpTestData(cls):
        cls.primaire = Section.objects.get(nom=choices.SECTION_PRIMAIRE)
        cls.secondaire = Section.objects.get(nom=choices.SECTION_SECONDAIRE)
        cls.sixieme = Classe.objects.create(nom="6ème AF", section=cls.primaire)
        cls.septieme = Classe.objects.create(nom="7ème AF", section=cls.secondaire)

        def employe(identifiant, poste, section=None):
            compte = Utilisateur.objects.create_user(identifiant, password="x")
            Employe.objects.create(nom=identifiant, prenom="X", poste=poste, section=section, utilisateur=compte)
            return compte

        cls.secretaire = employe("sec", "Secrétaire")
        cls.dir_primaire = employe("dirp", choices.POSTES_DIRECTION_SECTION[1], cls.primaire)
        cls.dir_secondaire = employe("dirs", choices.POSTES_DIRECTION_SECTION[2], cls.secondaire)
        cls.chef = employe("chef", choices.POSTE_DIRECTION_GENERALE)
        cls.caisse = employe("caisse", "Caissier(ère)")

    def setUp(self):
        super().setUp()
        self.dossier = Preinscription.objects.create(
            nom="Joseph", prenom="Naïka", date_naissance=date(2015, 3, 14), genre="Féminin", classe_demandee=self.sixieme,
            nom_parent="Marie-Claude Joseph", telephone_parent="3712 4455", adresse="Les Cayes",
            photo=image(400, 400, "p.jpg"), acte_naissance=pdf(),
        )
        self.autre = Preinscription.objects.create(
            nom="Pierre", prenom="Josué", date_naissance=date(2013, 5, 2), genre="Masculin", classe_demandee=self.septieme,
            nom_parent="Rose Pierre", telephone_parent="3811 2233",
        )

    def etape(self, dossier, action, **autres):
        return self.client.post(reverse("core:preinscription_etape", args=[dossier.pk]), {"action": action, **autres})

    def test_parcours_complet(self):
        # 1. Le secrétariat voit la demande et la transmet ; il ne peut pas décider
        self.client.force_login(self.secretaire)
        liste = self.client.get(reverse("core:preinscription_liste"))
        self.assertContains(liste, self.dossier.numero)
        self.assertContains(liste, self.autre.numero)
        self.assertEqual(self.etape(self.dossier, "accepter").status_code, 403)
        self.assertRedirects(self.etape(self.dossier, "transmettre"),
                             reverse("core:preinscription_fiche", args=[self.dossier.pk]))
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.etape, choices.ETAPE_CHEZ_LA_DIRECTION)

        # 2. La direction du primaire ne voit que sa section, et accepte
        self.client.force_login(self.dir_primaire)
        liste = self.client.get(reverse("core:preinscription_liste"))
        self.assertContains(liste, self.dossier.numero)
        self.assertNotContains(liste, self.autre.numero)
        self.assertEqual(self.client.get(reverse("core:preinscription_fiche", args=[self.autre.pk])).status_code, 404)
        self.assertContains(self.client.get(reverse("core:preinscription_fiche", args=[self.dossier.pk])), "Accepter")
        self.assertEqual(self.etape(self.dossier, "inscrire").status_code, 403)
        self.etape(self.dossier, "accepter", avis="Bon dossier, place disponible.")
        self.dossier.refresh_from_db()
        self.assertEqual((self.dossier.etape, self.dossier.decision_par), (choices.ETAPE_ACCEPTEE, self.dir_primaire))
        self.assertEqual(self.dossier.avis_direction, "Bon dossier, place disponible.")

        # La direction du secondaire ne peut pas décider pour le primaire
        self.client.force_login(self.dir_secondaire)
        self.assertEqual(self.etape(self.dossier, "refuser").status_code, 404)

        # 3. Le secrétariat inscrit : la fiche élève est créée dans la classe, avec la photo
        self.client.force_login(self.secretaire)
        reponse = self.etape(self.dossier, "inscrire")
        eleve = Eleve.objects.get(nom="Joseph", prenom="Naïka")
        self.assertRedirects(reponse, reverse("core:eleve_fiche", args=[eleve.pk]))
        self.assertEqual((eleve.classe, eleve.telephone_parent, eleve.date_naissance),
                         (self.sixieme, "3712 4455", date(2015, 3, 14)))
        self.assertRegex(eleve.photo.name, r"^photos/eleve/")
        self.assertNotEqual(eleve.photo.name, self.dossier.photo.name)
        self.dossier.refresh_from_db()
        self.assertEqual((self.dossier.etape, self.dossier.eleve), (choices.ETAPE_INSCRITE, eleve))
        # Plus rien à faire sur un dossier inscrit
        self.assertEqual(self.etape(self.dossier, "inscrire").status_code, 403)
        self.assertContains(self.client.get(reverse("core:classe_fiche", args=[self.sixieme.pk])), "Naïka")

    def test_directrice_en_chef_decide_partout_et_refuse(self):
        self.client.force_login(self.chef)
        self.client.post(reverse("core:preinscription_etape", args=[self.autre.pk]),
                         {"action": "refuser", "avis": "Plus de place en 7ème AF."}, follow=True)
        self.autre.refresh_from_db()
        self.assertEqual(self.autre.etape, choices.ETAPE_REFUSEE)
        self.assertNotContains(self.client.get(reverse("core:preinscription_liste")), self.autre.numero)
        self.assertContains(self.client.get(reverse("core:preinscription_liste") + "?etape=Refusée"), self.autre.numero)

    def test_pieces_et_photo_protegees(self):
        piece = reverse("core:piece", args=[self.dossier.pk, "acte_naissance"])
        photo = reverse("core:photo", args=["preinscription", self.dossier.pk])
        self.assertRedirects(self.client.get(piece), f"/connexion/?next={piece}", fetch_redirect_response=False)
        self.client.force_login(self.secretaire)
        reponse = self.client.get(piece)
        self.assertEqual((reponse.status_code, reponse["Content-Type"]), (200, "application/pdf"))
        self.assertIn("attachment", reponse["Content-Disposition"])
        self.assertEqual(self.client.get(photo).status_code, 200)
        self.assertEqual(self.client.get(reverse("core:piece", args=[self.dossier.pk, "photo"])).status_code, 404)
        self.client.force_login(self.dir_secondaire)
        self.assertEqual(self.client.get(piece).status_code, 404)
        self.assertEqual(self.client.get(photo).status_code, 404)

    def test_roles_sans_acces(self):
        professeur = Professeur.objects.create(nom="Blaise", prenom="Rose",
                                               utilisateur=Utilisateur.objects.create_user("rose", password="x"))
        parent = Utilisateur.objects.create_user("parent", password="x")
        parent.groups.add(Group.objects.get(name=roles.PARENT))
        for compte in (self.caisse, professeur.utilisateur, parent):
            with self.subTest(compte=compte.username):
                self.client.force_login(compte)
                self.assertEqual(self.client.get(reverse("core:preinscription_liste")).status_code, 403)
                self.assertEqual(self.etape(self.dossier, "transmettre").status_code, 403)

    def test_suppression_efface_les_fichiers(self):
        stockage = self.dossier.photo.storage
        fichiers = [self.dossier.photo.name, self.dossier.acte_naissance.name]
        self.client.force_login(self.secretaire)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("core:preinscription_supprimer", args=[self.dossier.pk]))
        self.assertFalse(Preinscription.objects.filter(pk=self.dossier.pk).exists())
        self.assertFalse(any(stockage.exists(nom) for nom in fichiers))

    def test_tableau_de_bord_et_modification(self):
        self.client.force_login(self.secretaire)
        reponse = self.client.get(reverse("core:dashboard"))
        self.assertContains(reponse, "demandes reçues, dossier à vérifier")
        self.assertContains(reponse, reverse("core:preinscription_liste"))
        reponse = self.client.post(reverse("core:preinscription_modifier", args=[self.autre.pk]), {
            "nom": "Pierre", "prenom": "Josué", "date_naissance": "2013-05-02", "genre": "Masculin",
            "classe_demandee": self.septieme.pk, "nom_parent": "Rose Pierre", "telephone_parent": "3811 2233",
            "rendez_vous": "2026-10-02T09:30", "note_interne": "Vient avec l'acte de naissance.",
        })
        self.assertRedirects(reponse, reverse("core:preinscription_fiche", args=[self.autre.pk]))
        self.autre.refresh_from_db()
        self.assertEqual(self.autre.note_interne, "Vient avec l'acte de naissance.")
        self.assertIsNotNone(self.autre.rendez_vous)


class MessagesDuSiteTests(TestCase):
    def test_message_envoye_puis_traite(self):
        reponse = self.client.post(reverse("site:contact"), {
            "nom": "Marie Joseph", "telephone": "3712 4455", "message": "Quelle est la date de la réunion des parents ?"})
        self.assertRedirects(reponse, reverse("site:contact"))
        message = MessageContact.objects.get()
        self.assertFalse(message.traite)

        secretaire = Utilisateur.objects.create_user("sec", password="x")
        Employe.objects.create(nom="Jean", prenom="Marie", poste="Secrétaire", utilisateur=secretaire)
        self.client.force_login(secretaire)
        self.assertContains(self.client.get(reverse("core:message_liste")), "réunion des parents")
        self.client.post(reverse("core:message_traite", args=[message.pk]))
        message.refresh_from_db()
        self.assertEqual((message.traite, message.traite_par), (True, secretaire))
        self.assertNotContains(self.client.get(reverse("core:message_liste")), "réunion des parents")

        caisse = Utilisateur.objects.create_user("caisse", password="x")
        Employe.objects.create(nom="Paul", prenom="Luc", poste="Comptable", utilisateur=caisse)
        self.client.force_login(caisse)
        self.assertEqual(self.client.get(reverse("core:message_liste")).status_code, 403)

    def test_robot_et_numero_obligatoire(self):
        self.client.post(reverse("site:contact"), {"nom": "Robot", "telephone": "3712 4455", "message": "x", "site_web": "spam"})
        reponse = self.client.post(reverse("site:contact"), {"nom": "Marie", "telephone": "", "message": "Bonjour"})
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(MessageContact.objects.exists())
