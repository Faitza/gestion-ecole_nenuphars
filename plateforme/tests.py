# plateforme/tests.py
# Plusieurs écoles sur le même site : chaque école a sa base, ses comptes, ses photos et
# sa mémoire ; rien ne passe d'une école à l'autre.
import shutil
import tempfile
from io import StringIO
from pathlib import Path

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.db import connections
from django.test import TestCase, override_settings

from core import roles
from core.models import Classe, Eleve, Utilisateur

from . import ecoles
from .creation import creer_ecole
from .models import Ecole

DOMAINE = "ecoles.test"
A = "nenuphars.ecoles.test"
B = "stjoseph.ecoles.test"
PLATEFORME = "ecoles.test"


class AvecDeuxEcoles(TestCase):
    """Deux écoles ouvertes, chacune avec sa base SQLite dans un dossier temporaire.

    Les tables des écoles sont créées avant le test ; ensuite, comme la base « default »,
    chaque base d'école est remise à son état de départ après chaque test."""
    ADRESSES = ["nenuphars", "stjoseph", "sterose"]

    @classmethod
    def setUpClass(cls):
        cls.dossier = Path(tempfile.mkdtemp())
        cls.reglages = override_settings(
            SAAS_DOMAINE=DOMAINE, ALLOWED_HOSTS=[DOMAINE, "." + DOMAINE],
            DOSSIER_BASES_ECOLES=cls.dossier / "bases", MEDIA_ROOT=str(cls.dossier / "media"),
            DOSSIER_SAUVEGARDES=cls.dossier / "sauvegardes")
        cls.reglages.enable()
        for adresse in cls.ADRESSES:
            ecoles.migrer(Ecole(sous_domaine=adresse, base=ecoles.nom_de_base(adresse)))
        # Indiquées ici et pas sur la classe : le lanceur des tests ne doit pas créer ces bases
        cls.databases = {"default", *(ecoles.nom_de_base(a) for a in cls.ADRESSES)}
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        for alias in [a for a in connections.settings if a.startswith("ecole_")]:
            connections[alias].close()
            del connections[alias]
            del connections.settings[alias]
        cls.reglages.disable()
        shutil.rmtree(cls.dossier, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.ecole_a, cls.directrice_a, _ = creer_ecole(
            Ecole(nom="Institution Les Nénuphars", nom_court="Les Nénuphars", sous_domaine="nenuphars",
                  ville="Les Cayes"), "Marie", "Pierre", "50937000001")
        cls.ecole_b, cls.directrice_b, _ = creer_ecole(
            Ecole(nom="Collège Saint-Joseph", nom_court="Saint-Joseph", sous_domaine="stjoseph", ville="Jacmel"),
            "Jean", "Louis", "50937000002")
        for ecole in (cls.ecole_a, cls.ecole_b):
            with ecoles.activer(ecole):
                Utilisateur.objects.filter(doit_changer_mot_de_passe=True).update(doit_changer_mot_de_passe=False)
                compte = Utilisateur.objects.get()
                compte.set_password("motdepasse-solide-123")
                compte.save()

    def setUp(self):
        cache.clear()

    def connecter(self, hote, identifiant):
        reponse = self.client.post("/connexion/", {"username": identifiant, "password": "motdepasse-solide-123"},
                                   HTTP_HOST=hote)
        return reponse


class CreationEcoleTests(AvecDeuxEcoles):
    def test_chaque_ecole_a_sa_base_et_le_compte_de_sa_direction(self):
        self.assertEqual(self.ecole_a.base, "ecole_nenuphars")
        self.assertTrue((self.dossier / "bases" / "ecole_nenuphars.sqlite3").exists())
        self.assertTrue((self.dossier / "bases" / "ecole_stjoseph.sqlite3").exists())
        with ecoles.activer(self.ecole_a):
            compte = Utilisateur.objects.get()
            self.assertEqual(compte.telephone, "50937000001")
            self.assertTrue(compte.groups.filter(name=roles.DIRECTRICE_EN_CHEF).exists())
            # Sections et rôles de départ créés par les migrations
            from core.models import Section
            self.assertEqual(Section.objects.count(), 3)
        # Aucun compte d'école dans la base de la plateforme
        self.assertFalse(Utilisateur.objects.using("default").filter(telephone="50937000001").exists())

    def test_la_meme_personne_peut_etre_dans_deux_ecoles(self):
        # Les numéros, noms de classes... sont uniques dans une école, pas sur toute la plateforme
        for ecole in (self.ecole_a, self.ecole_b):
            with ecoles.activer(ecole):
                Classe.objects.create(nom="7ème AF")
                self.assertEqual(Classe.objects.filter(nom="7ème AF").count(), 1)


class SeparationDesDonneesTests(AvecDeuxEcoles):
    def test_un_eleve_n_apparait_que_dans_son_ecole(self):
        with ecoles.activer(self.ecole_a):
            Eleve.objects.create(nom="Duval", prenom="Anaïse", genre="F", date_naissance="2014-03-02")
        self.connecter(A, "50937000001")
        self.assertContains(self.client.get("/gestion/eleves/", HTTP_HOST=A), "Duval")
        self.client.logout()
        self.connecter(B, "50937000002")
        reponse = self.client.get("/gestion/eleves/", HTTP_HOST=B)
        self.assertEqual(reponse.status_code, 200)
        self.assertNotContains(reponse, "Duval")

    def test_un_compte_ne_se_connecte_que_dans_son_ecole(self):
        reponse = self.connecter(B, "50937000001")
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Identifiant ou mot de passe incorrect")
        reponse = self.connecter(A, "50937000001")
        self.assertEqual(reponse.status_code, 302)

    def test_la_session_d_une_ecole_ne_vaut_rien_dans_une_autre(self):
        self.connecter(A, "50937000001")
        self.assertEqual(self.client.get("/gestion/eleves/", HTTP_HOST=A).status_code, 200)
        # Même navigateur, même cookie : l'autre école ne connaît pas cette session
        reponse = self.client.get("/gestion/eleves/", HTTP_HOST=B)
        self.assertEqual(reponse.status_code, 302)
        self.assertIn("/connexion/", reponse["Location"])

    def test_le_site_public_montre_l_ecole_de_l_adresse(self):
        reponse = self.client.get("/", HTTP_HOST=B)
        self.assertContains(reponse, "Collège Saint-Joseph")
        self.assertContains(reponse, "Jacmel")
        self.assertNotContains(reponse, "Nénuphars")
        self.assertContains(self.client.get("/", HTTP_HOST=A), "Les Nénuphars")
        self.assertContains(self.client.get("/connexion/", HTTP_HOST=B), "SAINT-JOSEPH")

    def test_les_photos_de_chaque_ecole_sont_dans_leur_dossier(self):
        with ecoles.activer(self.ecole_b):
            eleve = Eleve.objects.create(nom="Joseph", prenom="Rose", genre="F", date_naissance="2013-01-01")
            eleve.photo.save("photo.jpg", ContentFile(b"jpeg"), save=True)
            chemin = Path(eleve.photo.path)
        self.assertIn(Path(self.dossier, "media", "ecoles", "stjoseph"), chemin.parents)

    def test_la_memoire_est_propre_a_chaque_ecole(self):
        with ecoles.activer(self.ecole_a):
            cache.set("site:sections", ["A"])
        with ecoles.activer(self.ecole_b):
            self.assertIsNone(cache.get("site:sections"))

    def test_sauvegarde_d_une_ecole(self):
        with ecoles.activer(self.ecole_a):
            Eleve.objects.create(nom="Duval", prenom="Anaïse", genre="F", date_naissance="2014-03-02")
        call_command("ecole", "nenuphars", "sauvegarder", "--sans-verification", stdout=StringIO())
        fichiers = list((self.dossier / "sauvegardes" / "nenuphars").glob("nenuphars-*.zip"))
        self.assertEqual(len(fichiers), 1)
        import json
        import zipfile
        with zipfile.ZipFile(fichiers[0]) as archive:
            contenu = json.loads(archive.read("contenu.json"))
        self.assertEqual(contenu["lignes"]["core.Eleve"], 1)
        self.assertEqual(contenu["lignes"]["core.Utilisateur"], 1)
        self.assertNotIn("plateforme.Ecole", contenu["lignes"])


class AdressesTests(AvecDeuxEcoles):
    def test_adresse_inconnue(self):
        reponse = self.client.get("/", HTTP_HOST="inconnue.ecoles.test")
        self.assertEqual(reponse.status_code, 404)
        self.assertContains(reponse, "Aucune école à cette adresse", status_code=404)
        self.assertNotContains(reponse, "Nénuphars", status_code=404)

    def test_ecole_suspendue(self):
        Ecole.objects.filter(pk=self.ecole_b.pk).update(active=False)
        reponse = self.client.get("/", HTTP_HOST=B)
        self.assertEqual(reponse.status_code, 503)
        self.assertContains(reponse, "Collège Saint-Joseph", status_code=503)
        self.assertEqual(self.client.get("/", HTTP_HOST=A).status_code, 200)

    def test_sante_par_ecole(self):
        self.assertEqual(self.client.get("/sante/", HTTP_HOST=A).json()["etat"], "ok")
        self.assertEqual(self.client.get("/sante/", HTTP_HOST=PLATEFORME).json()["etat"], "ok")


class PlateformeTests(AvecDeuxEcoles):
    def setUp(self):
        super().setUp()
        self.admin = Utilisateur.objects.create_superuser("proprio", "proprio@example.com", "motdepasse-solide-123")

    def test_pages_reservees_aux_administrateurs(self):
        reponse = self.client.get("/ecoles/", HTTP_HOST=PLATEFORME)
        self.assertEqual(reponse.status_code, 302)
        Utilisateur.objects.create_user("simple", password="motdepasse-solide-123")
        reponse = self.connecter(PLATEFORME, "simple")
        self.assertContains(reponse, "Identifiant ou mot de passe incorrect")

    def test_les_pages_des_ecoles_n_existent_pas_sur_la_plateforme(self):
        self.assertEqual(self.client.get("/gestion/eleves/", HTTP_HOST=PLATEFORME).status_code, 404)
        self.assertContains(self.client.get("/", HTTP_HOST=PLATEFORME), "Espace administrateur")

    def test_liste_et_creation_d_une_ecole(self):
        self.assertEqual(self.connecter(PLATEFORME, "proprio").status_code, 302)
        reponse = self.client.get("/ecoles/", HTTP_HOST=PLATEFORME)
        self.assertContains(reponse, "Collège Saint-Joseph")
        self.assertContains(reponse, "stjoseph.ecoles.test")
        reponse = self.client.post("/ecoles/nouvelle/", {
            "nom": "École Sainte-Rose", "sous_domaine": "sterose", "ville": "Jérémie",
            "responsable_prenom": "Rose", "responsable_nom": "Michel", "responsable_telephone": "3700 0003",
        }, HTTP_HOST=PLATEFORME)
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "École Sainte-Rose est ouverte")
        mot_de_passe = reponse.context["mot_de_passe"]
        ecole = Ecole.objects.get(sous_domaine="sterose")
        with ecoles.activer(ecole):
            compte = Utilisateur.objects.get(telephone="50937000003")
            self.assertTrue(compte.check_password(mot_de_passe))
            self.assertTrue(compte.doit_changer_mot_de_passe)
        # Sa direction se connecte à son adresse et doit changer le mot de passe provisoire
        self.client.logout()
        reponse = self.client.post("/connexion/", {"username": "3700 0003", "password": mot_de_passe},
                                   HTTP_HOST="sterose.ecoles.test", follow=True)
        self.assertEqual(reponse.redirect_chain[-1][0], "/mot-de-passe/")

    def test_adresse_refusee(self):
        self.connecter(PLATEFORME, "proprio")
        for adresse in ("www", "Saint Joseph", "-abc", "stjoseph"):
            reponse = self.client.post("/ecoles/nouvelle/", {
                "nom": "X", "sous_domaine": adresse, "ville": "Y",
                "responsable_prenom": "A", "responsable_nom": "B", "responsable_telephone": "37000009",
            }, HTTP_HOST=PLATEFORME)
            self.assertEqual(reponse.status_code, 200)
            self.assertTrue(reponse.context["form"].errors.get("sous_domaine"), adresse)
        self.assertEqual(Ecole.objects.count(), 2)

    def test_suspendre_puis_rouvrir(self):
        self.connecter(PLATEFORME, "proprio")
        self.client.post(f"/ecoles/{self.ecole_b.pk}/etat/", HTTP_HOST=PLATEFORME)
        self.assertFalse(Ecole.objects.get(pk=self.ecole_b.pk).active)
        self.client.post(f"/ecoles/{self.ecole_b.pk}/etat/", HTTP_HOST=PLATEFORME)
        self.assertTrue(Ecole.objects.get(pk=self.ecole_b.pk).active)

    def test_modifier_les_coordonnees(self):
        self.connecter(PLATEFORME, "proprio")
        reponse = self.client.post(f"/ecoles/{self.ecole_b.pk}/", {
            "nom": "Collège Saint-Joseph", "nom_court": "Saint-Joseph", "ville": "Jacmel",
            "telephones": "+509 3700 1111", "sous_domaine": "autre",
        }, HTTP_HOST=PLATEFORME)
        self.assertEqual(reponse.status_code, 302)
        ecole = Ecole.objects.get(pk=self.ecole_b.pk)
        self.assertEqual(ecole.sous_domaine, "stjoseph")   # l'adresse ne change plus
        self.assertContains(self.client.get("/contact/", HTTP_HOST=B), "+509 3700 1111")
