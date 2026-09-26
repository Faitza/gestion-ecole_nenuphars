# core/tests.py
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from . import choices, roles
from .models import Classe, Eleve, Employe, Note, Paiement, Professeur, Section, Utilisateur
from .telephone import normaliser_telephone


class SectionsTests(TestCase):
    def test_chaque_classe_par_defaut_a_une_section(self):
        noms = [nom for nom, _ in choices.CLASSES_PAR_DEFAUT]
        self.assertEqual(sorted(noms), sorted(choices.SECTION_PAR_CLASSE))

    def test_la_septieme_est_au_secondaire(self):
        self.assertEqual(choices.SECTION_PAR_CLASSE["7ème AF"], choices.SECTION_SECONDAIRE)
        self.assertEqual(choices.SECTION_PAR_CLASSE["NSIV"], choices.SECTION_SECONDAIRE)
        self.assertEqual(choices.SECTION_PAR_CLASSE["6ème AF"], choices.SECTION_PRIMAIRE)

    def test_migrations_creent_sections_et_roles(self):
        self.assertEqual(list(Section.objects.values_list("nom", flat=True)), choices.SECTIONS_PAR_DEFAUT)
        self.assertEqual(set(Group.objects.values_list("name", flat=True)), set(roles.TOUS_LES_ROLES))


class ConnexionTests(TestCase):
    def setUp(self):
        self.compte = Utilisateur.objects.create_user(
            "mlafontant", email="nadia@example.com", password="Motdepasse-2026", telephone="+509 3712-3456",
        )

    def test_telephone_normalise(self):
        self.assertEqual(normaliser_telephone("3712 3456"), "50937123456")
        self.assertEqual(normaliser_telephone("+509 3712-3456"), "50937123456")
        self.assertEqual(self.compte.telephone, "50937123456")

    def test_meme_numero_ecrit_autrement_refuse(self):
        from django.core.exceptions import ValidationError
        autre = Utilisateur(username="autre", telephone="3712-3456")
        autre.set_unusable_password()
        with self.assertRaises(ValidationError):
            autre.full_clean()

    def test_connexion_avec_chaque_identifiant(self):
        for identifiant in ["mlafontant", "NADIA@example.com", "3712 3456", "+509 37 12 34 56"]:
            with self.subTest(identifiant=identifiant):
                reponse = self.client.post(reverse("core:login"), {"username": identifiant, "password": "Motdepasse-2026"})
                self.assertRedirects(reponse, reverse("core:espace"), fetch_redirect_response=False)
                self.client.logout()

    def test_mauvais_mot_de_passe(self):
        reponse = self.client.post(reverse("core:login"), {"username": "3712 3456", "password": "faux"})
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Identifiant ou mot de passe incorrect.")

    def test_ancienne_adresse_login(self):
        reponse = self.client.get("/login/?next=/eleves/")
        self.assertRedirects(reponse, "/connexion/?next=/eleves/", fetch_redirect_response=False)

    def test_page_protegee_renvoie_vers_la_connexion(self):
        reponse = self.client.get(reverse("core:eleve_liste"))
        self.assertRedirects(reponse, "/connexion/?next=/eleves/", fetch_redirect_response=False)

    def test_mot_de_passe_provisoire_a_changer(self):
        self.compte.doit_changer_mot_de_passe = True
        self.compte.save()
        self.client.force_login(self.compte)
        self.assertRedirects(self.client.get(reverse("core:espace")), reverse("core:mot_de_passe"))
        reponse = self.client.post(reverse("core:mot_de_passe"), {
            "old_password": "Motdepasse-2026", "new_password1": "Nenuphars-Cayes-77", "new_password2": "Nenuphars-Cayes-77",
        })
        self.assertRedirects(reponse, reverse("core:espace"))
        self.compte.refresh_from_db()
        self.assertFalse(self.compte.doit_changer_mot_de_passe)
        self.assertEqual(self.client.get(reverse("core:espace")).status_code, 200)


class RolesEtAccesTests(TestCase):
    """Droits repris du tableau « Droits d'accès » du cahier des charges."""

    @classmethod
    def setUpTestData(cls):
        cls.primaire = Section.objects.get(nom=choices.SECTION_PRIMAIRE)
        cls.secondaire = Section.objects.get(nom=choices.SECTION_SECONDAIRE)
        cls.sixieme = Classe.objects.create(nom="6ème AF", section=cls.primaire)
        cls.septieme = Classe.objects.create(nom="7ème AF", section=cls.secondaire)
        cls.eleve_pri = Eleve.objects.create(nom="Joseph", prenom="Anne", genre="Féminin", classe=cls.sixieme)
        cls.eleve_sec = Eleve.objects.create(nom="Pierre", prenom="Marc", genre="Masculin", classe=cls.septieme)
        cls.note_pri = Note.objects.create(eleve=cls.eleve_pri, matiere="Français", note=80, periode="1er Trimestre")
        cls.note_sec = Note.objects.create(eleve=cls.eleve_sec, matiere="Français", note=70, periode="1er Trimestre")

    def compte_employe(self, username, poste, section=None):
        compte = Utilisateur.objects.create_user(username, password="x")
        Employe.objects.create(nom=username, prenom="Test", poste=poste, section=section, utilisateur=compte)
        return compte

    def test_role_suit_le_poste(self):
        compte = self.compte_employe("sec", "Secrétaire")
        self.assertEqual(roles.roles_de(compte), {roles.SECRETARIAT})
        employe = compte.employe
        employe.poste = "Caissier(ère)"
        employe.save()
        compte = Utilisateur.objects.get(pk=compte.pk)
        self.assertEqual(roles.roles_de(compte), {roles.CAISSE})

    def test_compte_detache_ou_employe_supprime_perd_son_role(self):
        compte = self.compte_employe("cais", "Caissier(ère)")
        autre = Utilisateur.objects.create_user("autre", password="x")
        employe = compte.employe
        employe.utilisateur = autre
        employe.save()
        self.assertEqual(roles.roles_de(Utilisateur.objects.get(pk=compte.pk)), set())
        self.assertEqual(roles.roles_de(Utilisateur.objects.get(pk=autre.pk)), {roles.CAISSE})
        employe.delete()
        self.assertEqual(roles.roles_de(Utilisateur.objects.get(pk=autre.pk)), set())

    def test_professeur_a_son_role(self):
        compte = Utilisateur.objects.create_user("prof", password="x")
        Professeur.objects.create(nom="Blaise", prenom="Wilfrid", utilisateur=compte)
        self.assertEqual(roles.roles_de(compte), {roles.PROFESSEUR})

    def test_espace_selon_le_role(self):
        self.client.force_login(self.compte_employe("sec", "Secrétaire"))
        self.assertRedirects(self.client.get(reverse("core:espace")), reverse("core:dashboard"))

        parent = Utilisateur.objects.create_user("parent", password="x")
        parent.groups.add(Group.objects.get(name=roles.PARENT))
        self.client.force_login(parent)
        self.assertRedirects(self.client.get(reverse("core:dashboard")), reverse("core:espace"))
        self.assertContains(self.client.get(reverse("core:espace")), "Votre espace est en préparation")

    def test_parent_ne_voit_pas_la_gestion(self):
        parent = Utilisateur.objects.create_user("parent", password="x")
        parent.groups.add(Group.objects.get(name=roles.PARENT))
        self.client.force_login(parent)
        for nom in ["eleve_liste", "classe_liste", "professeur_liste", "employe_liste", "paiement_liste", "note_liste"]:
            with self.subTest(page=nom):
                self.assertEqual(self.client.get(reverse(f"core:{nom}")).status_code, 403)

    def test_secretariat_inscrit_mais_ne_touche_pas_aux_paiements(self):
        self.client.force_login(self.compte_employe("sec", "Secrétaire"))
        self.assertEqual(self.client.get(reverse("core:eleve_creer")).status_code, 200)
        self.assertEqual(self.client.get(reverse("core:professeur_creer")).status_code, 200)
        self.assertEqual(self.client.get(reverse("core:paiement_liste")).status_code, 200)
        self.assertEqual(self.client.get(reverse("core:paiement_creer")).status_code, 403)
        self.assertEqual(self.client.get(reverse("core:employe_liste")).status_code, 403)
        reponse = self.client.get(reverse("core:note_liste"))
        self.assertNotContains(reponse, reverse("core:note_creer"))

    def test_caisse_enregistre_les_paiements(self):
        self.client.force_login(self.compte_employe("cais", "Caissier(ère)"))
        reponse = self.client.post(reverse("core:paiement_creer"), {
            "eleve": self.eleve_pri.pk, "montant": "5000", "type_paiement": "Réinscription",
            "methode_paiement": "Espèces", "statut": "Payé",
        })
        self.assertRedirects(reponse, reverse("core:paiement_liste"))
        self.assertEqual(Paiement.objects.count(), 1)
        self.assertEqual(self.client.get(reverse("core:note_liste")).status_code, 403)

    def test_direction_de_section_limitee_a_sa_section(self):
        self.client.force_login(self.compte_employe("dirpri", "Directeur(trice) du primaire", self.primaire))
        reponse = self.client.get(reverse("core:eleve_liste"))
        self.assertContains(reponse, "Joseph")
        self.assertNotContains(reponse, "Pierre")
        self.assertEqual(self.client.get(reverse("core:note_modifier", args=[self.note_pri.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("core:note_modifier", args=[self.note_sec.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("core:eleve_creer")).status_code, 403)

        formulaire = self.client.get(reverse("core:note_creer")).context["form"]
        self.assertEqual(list(formulaire.fields["eleve"].queryset), [self.eleve_pri])
        reponse = self.client.post(reverse("core:note_creer"), {
            "eleve": self.eleve_sec.pk, "matiere": "Français", "note": "90", "periode": "1er Trimestre",
        })
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(Note.objects.filter(eleve=self.eleve_sec).count(), 1)

    def test_direction_ne_voit_pas_les_salaires(self):
        Employe.objects.create(nom="Surv", prenom="Test", poste="Surveillant(e)", section=self.primaire, salaire=12345)
        self.client.force_login(self.compte_employe("dirpri", "Directeur(trice) du primaire", self.primaire))
        reponse = self.client.get(reverse("core:employe_liste"))
        self.assertContains(reponse, "Surv")
        self.assertNotContains(reponse, "12345")

    def test_direction_sans_section_ne_voit_rien(self):
        self.client.force_login(self.compte_employe("dir", "Directeur(trice) du primaire"))
        reponse = self.client.get(reverse("core:eleve_liste"))
        self.assertNotContains(reponse, "Joseph")
        self.assertNotContains(reponse, "Pierre")

    def test_directrice_en_chef_voit_tout(self):
        Employe.objects.create(nom="Surv", prenom="Test", poste="Surveillant(e)", salaire=12345)
        self.client.force_login(self.compte_employe("chef", "Directeur(trice) en chef"))
        reponse = self.client.get(reverse("core:eleve_liste"))
        self.assertContains(reponse, "Joseph")
        self.assertContains(reponse, "Pierre")
        self.assertContains(self.client.get(reverse("core:employe_liste")), "12345")
        self.assertEqual(self.client.get(reverse("core:employe_creer")).status_code, 200)
