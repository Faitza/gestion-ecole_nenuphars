# core/tests_production.py
# Le site en ligne : limite de requêtes, envois trop lourds, pages d'erreur, adresse
# /sante/, double paiement, pages des longues listes, mémoire du site public et
# sauvegarde vérifiée par une vraie restauration.
import json
import tempfile
import zipfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db import connection
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from . import choices, sauvegardes
from .models import Classe, Eleve, Paiement, Section, Utilisateur

CACHE_MEMOIRE = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "tests-production"}}
LIMITES_BASSES = {"pages": (5, 60), "photos": (100, 60), "connexion": (3, 300), "formulaires_publics": (2, 600)}


@override_settings(CACHES=CACHE_MEMOIRE, LIMITES_REQUETES=LIMITES_BASSES)
class LimiteRequetesTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_trop_de_pages_donne_429(self):
        for _ in range(5):
            self.assertEqual(self.client.get("/").status_code, 200)
        reponse = self.client.get("/")
        self.assertEqual(reponse.status_code, 429)
        self.assertEqual(reponse["Retry-After"], "60")
        self.assertContains(reponse, "Trop de demandes", status_code=429)

    def test_autre_visiteur_pas_bloque(self):
        for _ in range(6):
            self.client.get("/")
        self.assertEqual(self.client.get("/", REMOTE_ADDR="10.0.0.2").status_code, 200)

    def test_photos_comptees_a_part(self):
        for _ in range(8):
            self.assertEqual(self.client.get("/activites/photos/999/vignette/").status_code, 404)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_sante_jamais_limitee(self):
        for _ in range(10):
            self.assertEqual(self.client.get("/sante/").status_code, 200)

    def test_connexion_limitee_par_compte(self):
        url = reverse("core:login")
        for _ in range(3):
            self.assertEqual(self.client.post(url, {"username": "directrice", "password": "faux"}).status_code, 200)
        self.assertEqual(self.client.post(url, {"username": "directrice", "password": "faux"}).status_code, 429)
        # Une autre personne du même wifi peut encore se connecter
        self.assertEqual(self.client.post(url, {"username": "secretaire", "password": "faux"}).status_code, 200)

    def test_formulaire_contact_limite(self):
        url = reverse("site:contact")
        donnees = {"nom": "Robot", "telephone": "3712 3456", "message": "Bonjour"}
        for _ in range(2):
            self.client.post(url, donnees)
        self.assertEqual(self.client.post(url, donnees).status_code, 429)

    def test_compte_connecte_compte_a_part(self):
        Utilisateur.objects.create_superuser("chef", password="x")
        for _ in range(6):
            self.client.get("/")   # l'adresse IP a atteint sa limite
        self.client.force_login(Utilisateur.objects.get(username="chef"))
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 200)


class TailleEnvoiTests(TestCase):
    @override_settings(TAILLE_MAX_ENVOI=1000)
    def test_envoi_trop_lourd_refuse_avant_lecture(self):
        reponse = self.client.post(reverse("site:contact"), data="x" * 5000, content_type="application/octet-stream")
        self.assertEqual(reponse.status_code, 413)
        self.assertContains(reponse, "trop lourds", status_code=413)


class PagesErreurTests(TestCase):
    def test_404_en_francais(self):
        reponse = self.client.get("/cette-page-n-existe-pas/")
        self.assertEqual(reponse.status_code, 404)
        self.assertContains(reponse, "Cette page n'existe pas", status_code=404)

    def test_500_sans_base_de_donnees(self):
        # La page 500 ne doit rien demander à la base : elle s'affiche même quand la base est en panne
        with CaptureQueriesContext(connection) as requetes:
            html = render_to_string("500.html")
        self.assertEqual(len(requetes), 0)
        self.assertIn("Réessayer", html)

    def test_page_expiree_pour_csrf(self):
        client = self.client_class(enforce_csrf_checks=True)
        reponse = client.post(reverse("core:login"), {"username": "a", "password": "b"})
        self.assertContains(reponse, "Le formulaire a expiré", status_code=403)


class SanteTests(TestCase):
    def test_tout_va_bien(self):
        reponse = self.client.get("/sante/")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()["etat"], "ok")
        self.assertNotIn("max-age=3", reponse.get("Cache-Control", ""))

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
    def test_cache_en_panne_donne_503(self):
        # Un cache qui ne garde rien : la vérification le voit
        reponse = self.client.get("/sante/")
        self.assertEqual(reponse.status_code, 503)
        self.assertEqual(reponse.json()["cache"], "en panne")


class DoublePaiementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.chef = Utilisateur.objects.create_superuser("chef", password="x")
        cls.classe = Classe.objects.create(nom="6ème AF", section=Section.objects.get(nom=choices.SECTION_PRIMAIRE))
        cls.eleve = Eleve.objects.create(nom="Joseph", prenom="Anne", genre="Féminin", classe=cls.classe)

    def setUp(self):
        self.client.force_login(self.chef)
        self.url = reverse("core:paiement_creer")

    def donnees(self, **autres):
        return {"eleve": self.eleve.pk, "montant": "2500", "type_paiement": choices.TYPES_PAIEMENT_CHOICES[0][0],
                "methode_paiement": choices.METHODES_PAIEMENT_CHOICES[0][0], "statut": "Payé", **autres}

    def test_formulaire_a_un_jeton(self):
        self.assertContains(self.client.get(self.url), 'name="jeton"')

    def test_meme_formulaire_envoye_deux_fois(self):
        self.client.post(self.url, self.donnees(jeton="a" * 32))
        reponse = self.client.post(self.url, self.donnees(jeton="a" * 32), follow=True)
        self.assertEqual(Paiement.objects.count(), 1)
        self.assertContains(reponse, "déjà enregistré")

    def test_paiement_identique_recent_a_confirmer(self):
        self.client.post(self.url, self.donnees(jeton="a" * 32))
        reponse = self.client.post(self.url, self.donnees(jeton="b" * 32))
        self.assertEqual(Paiement.objects.count(), 1)
        self.assertContains(reponse, "a déjà été enregistré")
        self.assertContains(reponse, 'name="confirmer_doublon"')
        self.client.post(self.url, self.donnees(jeton="b" * 32, confirmer_doublon="on"))
        self.assertEqual(Paiement.objects.count(), 2)

    def test_paiement_identique_ancien_sans_question(self):
        ancien = Paiement.objects.create(eleve=self.eleve, montant=Decimal("2500"),
                                         type_paiement=choices.TYPES_PAIEMENT_CHOICES[0][0],
                                         methode_paiement=choices.METHODES_PAIEMENT_CHOICES[0][0])
        Paiement.objects.filter(pk=ancien.pk).update(date_paiement=timezone.now() - timedelta(days=30))
        self.client.post(self.url, self.donnees(jeton="c" * 32))
        self.assertEqual(Paiement.objects.count(), 2)


class PaginationEtRequetesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.chef = Utilisateur.objects.create_superuser("chef", password="x")
        classe = Classe.objects.create(nom="7ème AF", section=Section.objects.get(nom=choices.SECTION_SECONDAIRE))
        Eleve.objects.bulk_create(
            Eleve(nom=f"Nom{i:03d}", prenom="Élève", genre="Féminin", classe=classe) for i in range(120))

    def setUp(self):
        self.client.force_login(self.chef)

    def test_liste_des_eleves_par_pages(self):
        reponse = self.client.get(reverse("core:eleve_liste"))
        self.assertEqual(len(reponse.context["eleves"]), 50)
        self.assertContains(reponse, "1 à 50 sur 120")
        reponse = self.client.get(reverse("core:eleve_liste"), {"page": 3})
        self.assertEqual(len(reponse.context["eleves"]), 20)

    def test_recherche_gardee_d_une_page_a_l_autre(self):
        reponse = self.client.get(reverse("core:eleve_liste"), {"q": "Nom", "page": 1})
        self.assertContains(reponse, "?q=Nom&amp;page=2")

    def test_page_mal_ecrite(self):
        self.assertEqual(self.client.get(reverse("core:eleve_liste"), {"page": "abc"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("core:eleve_liste"), {"page": 999}).status_code, 200)

    def test_nombre_de_requetes_ne_depend_pas_du_nombre_d_eleves(self):
        # Une requête par élève affiché (N+1) ralentirait tout : le nombre reste fixe
        self.client.get(reverse("core:eleve_liste"))
        with CaptureQueriesContext(connection) as requetes:
            self.client.get(reverse("core:eleve_liste"))
        self.assertLess(len(requetes), 15)


@override_settings(CACHES=CACHE_MEMOIRE, DUREE_MEMOIRE_SITE_PUBLIC=3600)
class MemoireSitePublicTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_classes_gardees_puis_oubliees_quand_elles_changent(self):
        self.client.get("/")
        with CaptureQueriesContext(connection) as avant:
            self.client.get("/")
        Classe.objects.create(nom="NS I", section=Section.objects.get(nom=choices.SECTION_SECONDAIRE))
        self.assertContains(self.client.get(reverse("site:niveaux")), "NS I")
        self.assertFalse(any("core_classe" in r["sql"] and "core_section" in r["sql"] for r in avant.captured_queries))


class SauvegardeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        classe = Classe.objects.create(nom="6ème AF", section=Section.objects.get(nom=choices.SECTION_PRIMAIRE))
        cls.eleve = Eleve.objects.create(nom="Joseph", prenom="Anne", genre="Féminin", classe=classe)
        Paiement.objects.create(eleve=cls.eleve, montant=Decimal("1000"), type_paiement=choices.TYPES_PAIEMENT_CHOICES[0][0],
                                methode_paiement=choices.METHODES_PAIEMENT_CHOICES[0][0])

    def setUp(self):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        self.dossier = Path(dossier.name)
        reglage = self.settings(MEDIA_ROOT=str(self.dossier / "media"))
        reglage.enable()
        self.addCleanup(reglage.disable)
        tampon = BytesIO()
        Image.new("RGB", (40, 40), (200, 30, 30)).save(tampon, "JPEG")
        self.eleve.photo.save("photo.jpg", ContentFile(tampon.getvalue()))

    def test_sauvegarde_se_restaure_entierement(self):
        chemin, contenu = sauvegardes.sauvegarder(self.dossier / "sauvegardes")
        self.assertEqual(contenu["lignes"]["core.Eleve"], 1)
        self.assertEqual(contenu["fichiers"], [self.eleve.photo.name])
        problemes, _, lignes = sauvegardes.verifier(chemin)
        self.assertEqual(problemes, [])
        self.assertEqual(lignes["core.Paiement"], 1)

    def test_photo_perdue_dans_la_sauvegarde_est_vue(self):
        chemin, _ = sauvegardes.sauvegarder(self.dossier / "sauvegardes")
        abimee = self.dossier / "abimee.zip"
        with zipfile.ZipFile(chemin) as source, zipfile.ZipFile(abimee, "w") as copie:
            for nom in source.namelist():
                if not nom.startswith("media/"):
                    copie.writestr(nom, source.read(nom))
        problemes, _, _ = sauvegardes.verifier(abimee)
        self.assertTrue(any("Fichier manquant" in p for p in problemes), problemes)

    def test_ligne_perdue_dans_la_sauvegarde_est_vue(self):
        chemin, _ = sauvegardes.sauvegarder(self.dossier / "sauvegardes")
        abimee = self.dossier / "abimee.zip"
        with zipfile.ZipFile(chemin) as source, zipfile.ZipFile(abimee, "w") as copie:
            for nom in source.namelist():
                contenu = source.read(nom)
                if nom == "donnees.json":
                    contenu = json.dumps([o for o in json.loads(contenu) if o["model"] != "core.paiement"]).encode()
                copie.writestr(nom, contenu)
        problemes, _, _ = sauvegardes.verifier(abimee)
        self.assertIn("core.Paiement : 1 lignes sauvegardées, 0 restaurées", problemes)

    def test_anciennes_sauvegardes_effacees(self):
        dossier = self.dossier / "sauvegardes"
        dossier.mkdir()
        for jour in range(1, 6):
            (dossier / f"nenuphars-2026100{jour}-020000.zip").write_bytes(b"")
        effacees = sauvegardes.supprimer_anciennes(3, dossier)
        self.assertEqual([f.name for f in effacees], ["nenuphars-20261001-020000.zip", "nenuphars-20261002-020000.zip"])
