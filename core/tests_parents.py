# core/tests_parents.py
# Comptes parents : code d'accès remis par le secrétariat, création du compte
# par le parent, et espace parent limité à ses enfants.
import tempfile
from datetime import date

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from . import choices, parents, roles, views_parents
from .models import Classe, Eleve, Employe, Note, Paiement, Parent, Preinscription, Professeur, Section, Utilisateur

MOT_DE_PASSE = "Nenuphar-Bleu-2026"


class AvecComptes(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.primaire = Section.objects.get(nom=choices.SECTION_PRIMAIRE)
        cls.secondaire = Section.objects.get(nom=choices.SECTION_SECONDAIRE)
        cls.troisieme = Classe.objects.create(nom="3ème AF", section=cls.primaire)
        cls.septieme = Classe.objects.create(nom="7ème AF", section=cls.secondaire)
        cls.naika = Eleve.objects.create(nom="Joseph", prenom="Naïka", genre="Féminin", classe=cls.septieme,
                                         nom_parent_tuteur="Marie-Claude Joseph", telephone_parent="3712 4455")
        cls.wilson = Eleve.objects.create(nom="Joseph", prenom="Wilson", genre="Masculin", classe=cls.troisieme,
                                          nom_parent_tuteur="Marie-Claude Joseph", telephone_parent="+509 3712-4455")
        cls.autre = Eleve.objects.create(nom="Pierre", prenom="Josué", genre="Masculin", classe=cls.septieme,
                                         nom_parent_tuteur="Rose Pierre", telephone_parent="3811 2233")
        cls.secretaire = Utilisateur.objects.create_user("sec", password="x")
        Employe.objects.create(nom="Jean", prenom="Marie", poste="Secrétaire", utilisateur=cls.secretaire)
        cls.direction = Utilisateur.objects.create_user("dir", password="x")
        Employe.objects.create(nom="Célestin", prenom="Rose", poste=choices.POSTES_DIRECTION_SECTION[1],
                               section=cls.primaire, utilisateur=cls.direction)

    def setUp(self):
        cache.clear()  # le compteur d'essais ratés

    def famille(self, eleve):
        return parents.parent_de_l_eleve(eleve)

    def etape1(self, code, telephone):
        return self.client.post(reverse("core:inscription"), {"code": code, "telephone": telephone})

    def etape2(self, follow=False, **donnees):
        return self.client.post(reverse("core:inscription_mot_de_passe"), donnees, follow=follow)


class CodeDAccesTests(AvecComptes):
    def test_code_lisible_et_recopiable(self):
        code = parents.nouveau_code()
        self.assertRegex(code, r"^NEN-[A-Z2-9]{4}-[A-Z2-9]{2}$")
        self.assertFalse(set(code[4:]) & set("01OIL"))
        for ecrit in ("nen 4k7p 29", "NEN-4K7P-29", "4K7P29", " 4k7p-29 "):
            self.assertEqual(parents.lire_code(ecrit), "NEN-4K7P-29")
        self.assertIsNone(parents.lire_code("NEN-4K7P"))

    def test_freres_et_soeurs_meme_famille_meme_code(self):
        famille = self.famille(self.naika)
        code = famille.code_acces
        self.assertEqual(self.famille(self.wilson), famille)  # même numéro écrit autrement
        famille.refresh_from_db()
        self.assertEqual(famille.code_acces, code)
        self.assertEqual(set(famille.enfants.all()), {self.naika, self.wilson})
        self.assertNotEqual(self.famille(self.autre).code_acces, code)

    def test_sans_telephone_pas_de_famille(self):
        sans = Eleve.objects.create(nom="Noël", prenom="Luc", genre="Masculin", telephone_parent="")
        self.assertIsNone(self.famille(sans))
        self.famille(self.naika)
        from django.core.exceptions import ValidationError
        for telephone in ("", "509 3712-4455"):
            with self.subTest(telephone=telephone), self.assertRaises(ValidationError):
                Parent(nom="X", telephone=telephone).full_clean()

    def test_telephone_corrige_l_ancien_code_ne_sert_plus(self):
        ancienne = self.famille(self.autre)
        self.autre.telephone_parent = "3811 9999"
        self.autre.save()
        nouvelle = self.famille(self.autre)
        self.assertNotEqual(nouvelle, ancienne)
        self.assertFalse(Parent.objects.filter(pk=ancienne.pk).exists())

    def test_inscription_de_l_eleve_donne_le_code(self):
        dossier = Preinscription.objects.create(
            nom="Désir", prenom="Kerline", date_naissance=date(2016, 1, 5), genre="Féminin", classe_demandee=self.troisieme,
            nom_parent="Anne Désir", telephone_parent="3714 5566", etape=choices.ETAPE_ACCEPTEE,
        )
        self.client.force_login(self.secretaire)
        reponse = self.client.post(reverse("core:preinscription_etape", args=[dossier.pk]), {"action": "inscrire"},
                                   follow=True)
        eleve = Eleve.objects.get(nom="Désir")
        famille = eleve.parents.get()
        self.assertRedirects(reponse, reverse("core:eleve_fiche", args=[eleve.pk]))
        self.assertContains(reponse, famille.code_acces)  # dans le message et dans le bloc « Accès parent »
        self.assertContains(reponse, reverse("core:parent_acces", args=[famille.pk]))
        self.assertEqual(famille.nom, "Anne Désir")


class CreerMonCompteTests(AvecComptes):
    def test_parcours_complet(self):
        famille = self.famille(self.naika)
        self.famille(self.wilson)
        code = famille.code_acces

        # Mauvais code, ou bon code avec un autre téléphone : refusé sans dire lequel est faux
        for mauvais in [("NEN-AAAA-22", "3712 4455"), (code, "3811 2233")]:
            reponse = self.etape1(*mauvais)
            self.assertContains(reponse, "ne vont pas ensemble")

        # Le code peut être tapé en minuscules, le téléphone avec l'indicatif
        reponse = self.etape1(code.lower().replace("-", " "), "+509 37 12 44 55")
        self.assertRedirects(reponse, reverse("core:inscription_mot_de_passe"))
        page = self.client.get(reverse("core:inscription_mot_de_passe"))
        self.assertContains(page, "Naïka Joseph")
        self.assertContains(page, "Wilson Joseph")
        self.assertNotContains(page, "Josué")

        self.assertContains(self.etape2(mot_de_passe1=MOT_DE_PASSE, mot_de_passe2="autre"), "pas les mêmes")
        self.assertContains(self.etape2(mot_de_passe1="12345678", mot_de_passe2="12345678"), "entièrement numérique")
        self.assertFalse(Utilisateur.objects.filter(parent__isnull=False).exists())

        reponse = self.etape2(mot_de_passe1=MOT_DE_PASSE, mot_de_passe2=MOT_DE_PASSE, follow=True)
        self.assertRedirects(reponse, reverse("core:parent_espace"))
        self.assertContains(reponse, "Naïka et Wilson apparaissent maintenant")
        famille.refresh_from_db()
        compte = famille.utilisateur
        self.assertIsNone(famille.code_acces)
        self.assertEqual(roles.roles_de(compte), {roles.PARENT})
        self.assertEqual((compte.first_name, compte.last_name), ("Marie-Claude", "Joseph"))

        # Le code ne sert qu'une fois ; ensuite on se connecte avec son téléphone
        self.client.logout()
        self.assertContains(self.etape1(code, "3712 4455"), "ne vont pas ensemble")
        self.assertTrue(self.client.login(username="3712 4455", password=MOT_DE_PASSE))
        self.assertRedirects(self.client.get(reverse("core:espace")), reverse("core:parent_espace"))

    def test_sans_passer_par_le_code(self):
        self.assertRedirects(self.client.get(reverse("core:inscription_mot_de_passe")), reverse("core:inscription"))

    def test_trop_d_essais(self):
        code = self.famille(self.naika).code_acces
        for _ in range(views_parents.ESSAIS_MAX):
            self.etape1("NEN-AAAA-22", "3712 4455")
        reponse = self.etape1(code, "3712 4455")
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Trop d'essais")
        cache.clear()
        self.assertRedirects(self.etape1(code, "3712 4455"), reverse("core:inscription_mot_de_passe"))

    def test_professeur_qui_est_aussi_parent(self):
        compte = Utilisateur.objects.create_user("prof", password="Prof-Nenuphar-1", telephone="3811 2233")
        Professeur.objects.create(nom="Pierre", prenom="Rose", utilisateur=compte)
        code = self.famille(self.autre).code_acces
        self.etape1(code, "3811 2233")
        self.assertContains(self.client.get(reverse("core:inscription_mot_de_passe")), "déjà un compte")
        self.assertContains(self.etape2(mot_de_passe="faux"), "Mot de passe incorrect")
        self.etape2(mot_de_passe="Prof-Nenuphar-1")

        self.assertEqual(Parent.objects.get(utilisateur=compte).enfants.get(), self.autre)
        self.assertEqual(roles.roles_de(Utilisateur.objects.get(pk=compte.pk)), {roles.PROFESSEUR, roles.PARENT})
        # Son espace reste celui du professeur ; ses enfants sont dans « Mes enfants »
        espace = self.client.get(reverse("core:espace"))
        self.assertContains(espace, reverse("core:parent_espace"))
        self.assertContains(espace, "Mes enfants")
        self.assertContains(self.client.get(reverse("core:parent_espace")), "Josué")

    def test_deja_connecte(self):
        self.client.force_login(self.secretaire)
        self.assertRedirects(self.client.get(reverse("core:inscription")), reverse("core:espace"),
                             fetch_redirect_response=False)


class EspaceParentTests(AvecComptes):
    def setUp(self):
        super().setUp()
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        reglage = self.settings(MEDIA_ROOT=dossier.name)
        reglage.enable()
        self.addCleanup(reglage.disable)

        self.famille(self.wilson)
        famille = self.famille(self.naika)
        self.compte = parents.creer_compte(famille, MOT_DE_PASSE)
        annee = choices.annee_scolaire_courante()
        Note.objects.create(eleve=self.naika, matiere="Mathématiques", note=82, periode="1er Trimestre", annee_scolaire=annee)
        Note.objects.create(eleve=self.naika, matiere="Français", note="76.5", periode="1er Trimestre", annee_scolaire=annee)
        Note.objects.create(eleve=self.naika, matiere="Créole", note=40, periode="1er Trimestre", annee_scolaire="2019-2020")
        Note.objects.create(eleve=self.autre, matiere="Mathématiques", note=33, periode="1er Trimestre", annee_scolaire=annee)
        Paiement.objects.create(eleve=self.naika, montant=3000, type_paiement=choices.TYPES_PAIEMENT[0],
                                methode_paiement=choices.METHODES_PAIEMENT[0], statut="Payé")
        Paiement.objects.create(eleve=self.autre, montant=9999, type_paiement=choices.TYPES_PAIEMENT[0],
                                methode_paiement=choices.METHODES_PAIEMENT[0], statut="Payé")
        self.client.force_login(self.compte)

    def test_notes_et_paiements_de_ses_enfants(self):
        page = self.client.get(reverse("core:parent_espace"))
        self.assertContains(page, "Naïka")
        self.assertContains(page, "Wilson")
        self.assertContains(page, "76,5")
        self.assertContains(page, "79,25")  # moyenne générale de l'année
        self.assertContains(page, "3000 HTG")
        self.assertNotContains(page, "Créole")  # note d'une autre année
        self.assertNotContains(page, "Josué")
        self.assertNotContains(page, "9999")

        wilson = self.client.get(reverse("core:parent_enfant", args=[self.wilson.pk]))
        self.assertContains(wilson, "Pas encore de notes")
        self.assertEqual(self.client.get(reverse("core:parent_enfant", args=[self.autre.pk])).status_code, 404)

    def test_photos_de_ses_enfants_seulement(self):
        from site_public.tests import image
        for eleve in (self.naika, self.autre):
            eleve.photo.save("p.jpg", image(300, 300, "p.jpg"))
        self.assertEqual(self.client.get(reverse("core:photo", args=["eleve", self.naika.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("core:photo", args=["eleve", self.autre.pk])).status_code, 404)

    def test_pas_de_gestion_pour_un_parent(self):
        self.assertRedirects(self.client.get(reverse("core:dashboard")), reverse("core:espace"),
                             target_status_code=302)
        for nom in ["eleve_liste", "paiement_liste", "note_liste", "parent_liste", "preinscription_liste"]:
            with self.subTest(page=nom):
                self.assertEqual(self.client.get(reverse(f"core:{nom}")).status_code, 403)
        self.assertEqual(self.client.get(reverse("core:eleve_fiche", args=[self.naika.pk])).status_code, 403)
        menu = self.client.get(reverse("core:parent_espace"))
        self.assertContains(menu, "Mes enfants")
        self.assertNotContains(menu, "Mon espace")

    def test_famille_supprimee_perd_son_role(self):
        Parent.objects.get(utilisateur=self.compte).delete()
        self.assertEqual(roles.roles_de(Utilisateur.objects.get(pk=self.compte.pk)), set())


class SecretariatTests(AvecComptes):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.secretaire)

    def test_creer_l_acces_depuis_la_fiche_de_l_eleve(self):
        fiche = self.client.get(reverse("core:eleve_fiche", args=[self.autre.pk]))
        self.assertContains(fiche, "Créer l'accès parent")
        reponse = self.client.post(reverse("core:eleve_acces_parent", args=[self.autre.pk]))
        famille = self.autre.parents.get()
        self.assertRedirects(reponse, reverse("core:parent_acces", args=[famille.pk]))
        fiche_acces = self.client.get(reverse("core:parent_acces", args=[famille.pk]))
        self.assertContains(fiche_acces, famille.code_acces)
        self.assertContains(fiche_acces, "http://testserver/inscription/")

        sans = Eleve.objects.create(nom="Noël", prenom="Luc", genre="Masculin")
        reponse = self.client.post(reverse("core:eleve_acces_parent", args=[sans.pk]), follow=True)
        self.assertContains(reponse, "Ajoutez d&#x27;abord le téléphone du parent")

    def test_liste_et_nouveau_code(self):
        famille = self.famille(self.naika)
        active = self.famille(self.autre)
        parents.creer_compte(active, MOT_DE_PASSE)
        liste = self.client.get(reverse("core:parent_liste"), {"statut": "code"})
        self.assertContains(liste, "Marie-Claude Joseph")
        self.assertNotContains(liste, "Rose Pierre")
        self.assertContains(self.client.get(reverse("core:parent_liste"), {"q": "Josué"}), "Rose Pierre")
        self.assertContains(self.client.get(reverse("core:dashboard")), "1</strong> code parent pas encore utilisé")

        ancien = famille.code_acces
        self.client.post(reverse("core:parent_nouveau_code", args=[famille.pk]))
        famille.refresh_from_db()
        self.assertNotEqual(famille.code_acces, ancien)
        self.assertIsNone(parents.trouver(ancien, "3712 4455"))

    def test_mot_de_passe_oublie(self):
        famille = self.famille(self.naika)
        compte = parents.creer_compte(famille, MOT_DE_PASSE)
        self.client.post(reverse("core:parent_nouveau_mot_de_passe", args=[famille.pk]))
        page = self.client.get(reverse("core:parent_acces", args=[famille.pk]))
        provisoire = page.context["mot_de_passe"]
        self.assertTrue(provisoire)
        compte.refresh_from_db()
        self.assertTrue(compte.check_password(provisoire))
        self.assertTrue(compte.doit_changer_mot_de_passe)

        # Un compte qui sert aussi au personnel n'est pas réinitialisé par le secrétariat
        prof = Utilisateur.objects.create_user("prof", password="x", telephone="3811 2233")
        Professeur.objects.create(nom="Pierre", prenom="Rose", utilisateur=prof)
        autre = self.famille(self.autre)
        parents.relier(autre, prof)
        self.client.post(reverse("core:parent_nouveau_mot_de_passe", args=[autre.pk]))
        prof.refresh_from_db()
        self.assertTrue(prof.check_password("x"))

    def test_la_direction_ne_gere_pas_les_comptes_parents(self):
        self.client.force_login(self.direction)
        famille = self.famille(self.naika)
        self.assertEqual(self.client.get(reverse("core:parent_liste")).status_code, 403)
        self.assertEqual(self.client.get(reverse("core:parent_acces", args=[famille.pk])).status_code, 403)

