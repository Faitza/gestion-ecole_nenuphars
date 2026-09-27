# core/tests.py
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from . import choices, roles
from .models import Affectation, Classe, Cours, Creneau, Eleve, Employe, Note, Paiement, Professeur, Section, Utilisateur
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
        self.assertRedirects(reponse, "/connexion/?next=/gestion/eleves/", fetch_redirect_response=False)

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
        self.assertEqual(reponse.status_code, 200)
        self.assertNotContains(reponse, reverse("core:note_modifier", args=[self.note_pri.pk]))

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

        # La direction corrige une note de sa section, sans pouvoir la donner à un élève d'une autre section
        formulaire = self.client.get(reverse("core:note_modifier", args=[self.note_pri.pk])).context["form"]
        self.assertEqual(list(formulaire.fields["eleve"].queryset), [self.eleve_pri])
        reponse = self.client.post(reverse("core:note_modifier", args=[self.note_pri.pk]), {
            "eleve": self.eleve_sec.pk, "matiere": "Français", "note": "90", "periode": "1er Trimestre",
        })
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(Note.objects.filter(eleve=self.eleve_sec).count(), 1)
        reponse = self.client.post(reverse("core:note_modifier", args=[self.note_pri.pk]), {
            "eleve": self.eleve_pri.pk, "matiere": "Français", "note": "85", "periode": "1er Trimestre",
        })
        self.assertRedirects(reponse, reverse("core:note_liste"))
        self.note_pri.refresh_from_db()
        self.assertEqual(self.note_pri.note, 85)

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

    def test_directrice_en_chef_et_admin_lisent_les_notes_sans_les_saisir(self):
        admin = Utilisateur.objects.create_superuser("admin", password="x")
        for compte in [self.compte_employe("chef", "Directeur(trice) en chef"), admin]:
            with self.subTest(compte=compte.username):
                self.client.force_login(compte)
                reponse = self.client.get(reverse("core:note_liste"))
                self.assertContains(reponse, "Joseph")
                self.assertContains(reponse, "Pierre")
                self.assertNotContains(reponse, reverse("core:note_modifier", args=[self.note_pri.pk]))
                self.assertEqual(self.client.get(reverse("core:note_modifier", args=[self.note_pri.pk])).status_code, 403)
                self.assertEqual(self.client.post(reverse("core:note_supprimer", args=[self.note_pri.pk])).status_code, 403)
                self.assertEqual(self.client.get(reverse("core:saisie_notes")).status_code, 403)
        # Dans /admin/ aussi, les notes sont en lecture seule
        self.assertEqual(self.client.get("/admin/core/note/add/").status_code, 403)
        self.assertEqual(self.client.get(f"/admin/core/note/{self.note_pri.pk}/change/").status_code, 200)
        self.assertEqual(self.client.post(f"/admin/core/note/{self.note_pri.pk}/change/", {"note": "10"}).status_code, 403)
        self.note_pri.refresh_from_db()
        self.assertEqual(self.note_pri.note, 80)


class InscriptionProfesseursTests(TestCase):
    """Module professeurs : la secrétaire inscrit, la direction valide, le professeur se connecte."""

    @classmethod
    def setUpTestData(cls):
        cls.kinder = Section.objects.get(nom=choices.SECTION_KINDERGARTEN)
        cls.primaire = Section.objects.get(nom=choices.SECTION_PRIMAIRE)
        cls.secondaire = Section.objects.get(nom=choices.SECTION_SECONDAIRE)
        cls.k2 = Classe.objects.create(nom="2ème Année Kinder", section=cls.kinder)
        cls.sixieme = Classe.objects.create(nom="6ème AF", section=cls.primaire)
        cls.septieme = Classe.objects.create(nom="7ème AF", section=cls.secondaire)
        cls.nsi = Classe.objects.create(nom="NSI", section=cls.secondaire)
        cls.heures = list(Creneau.objects.filter(section=cls.secondaire, est_un_cours=True))

    def setUp(self):
        self.secretaire = Utilisateur.objects.create_user("secretaire", password="x")
        Employe.objects.create(nom="Auguste", prenom="Nadège", poste="Secrétaire", utilisateur=self.secretaire)
        self.client.force_login(self.secretaire)

    def inscrire(self, section, nom, telephone, **extra):
        donnees = {"section": section.pk, "nom": nom, "prenom": "Test", "telephone": telephone, **extra}
        return self.client.post(reverse("core:professeur_creer"), donnees)

    def lignes_de_cours(self, *lignes):
        donnees = {"cours-TOTAL_FORMS": str(len(lignes)), "cours-INITIAL_FORMS": "0"}
        for i, (matiere, classe, jour, creneau) in enumerate(lignes):
            donnees.update({f"cours-{i}-matiere": matiere, f"cours-{i}-classe": classe.pk,
                            f"cours-{i}-jour": jour, f"cours-{i}-creneau": creneau.pk})
        return donnees

    def test_horaires_du_secondaire_crees(self):
        self.assertEqual([c.nom for c in self.heures], ["1re heure", "2e heure", "3e heure", "4e heure", "5e heure"])
        self.assertEqual(self.heures[0].duree_minutes, 55)

    def test_choix_de_la_section_d_abord(self):
        reponse = self.client.get(reverse("core:professeur_creer"))
        self.assertContains(reponse, "?section=")
        self.assertNotContains(reponse, "Inscrire et créer le compte")
        reponse = self.client.get(reverse("core:professeur_creer"), {"section": self.secondaire.pk})
        self.assertContains(reponse, "Cours de la semaine")

    def test_inscription_kindergarten_cree_le_compte(self):
        reponse = self.inscrire(self.kinder, "Gédéon", "3712 0001", **{"aff-classe": self.k2.pk, "aff-role": choices.ROLE_TITULAIRE})
        professeur = Professeur.objects.get(nom="Gédéon")
        self.assertRedirects(reponse, reverse("core:professeur_acces", args=[professeur.pk]), fetch_redirect_response=False)
        self.assertEqual(professeur.section, self.kinder)
        self.assertEqual(professeur.affectation_active.classe, self.k2)
        self.assertEqual(list(professeur.classes.all()), [self.k2])
        compte = professeur.utilisateur
        self.assertEqual(compte.telephone, "50937120001")
        self.assertTrue(compte.doit_changer_mot_de_passe)
        self.assertEqual(roles.roles_de(compte), {roles.PROFESSEUR})

        # Le mot de passe provisoire s'affiche une seule fois, et il fonctionne
        page = self.client.get(reverse("core:professeur_acces", args=[professeur.pk]))
        mot_de_passe = page.context["mot_de_passe"]
        self.assertRegex(mot_de_passe, r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")
        self.assertIsNone(self.client.get(reverse("core:professeur_acces", args=[professeur.pk])).context["mot_de_passe"])
        self.client.logout()
        reponse = self.client.post(reverse("core:login"), {"username": "3712 0001", "password": mot_de_passe})
        self.assertRedirects(reponse, reverse("core:espace"), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("core:espace")), reverse("core:mot_de_passe"))

    def test_kindergarten_deux_maitresses_au_plus(self):
        self.inscrire(self.kinder, "Gédéon", "3712 0001", **{"aff-classe": self.k2.pk, "aff-role": choices.ROLE_TITULAIRE})
        reponse = self.inscrire(self.kinder, "Autre", "3712 0002", **{"aff-classe": self.k2.pk, "aff-role": choices.ROLE_TITULAIRE})
        self.assertContains(reponse, "a déjà une titulaire")
        self.inscrire(self.kinder, "Métellus", "3712 0003", **{"aff-classe": self.k2.pk, "aff-role": choices.ROLE_DEUXIEME_MAITRESSE})
        self.assertEqual(Affectation.objects.filter(classe=self.k2, date_fin__isnull=True).count(), 2)
        reponse = self.inscrire(self.kinder, "Troisième", "3712 0004", **{"aff-classe": self.k2.pk, "aff-role": choices.ROLE_DEUXIEME_MAITRESSE})
        self.assertContains(reponse, "a déjà ses deux maîtresses")
        self.assertFalse(Professeur.objects.filter(nom__in=["Autre", "Troisième"]).exists())

    def test_primaire_un_seul_professeur_remplacement_confirme(self):
        self.inscrire(self.primaire, "Lamour", "3712 0001", **{"aff-classe": self.sixieme.pk})
        ancien = Professeur.objects.get(nom="Lamour")
        reponse = self.inscrire(self.primaire, "Lafontant", "3712 0002", **{"aff-classe": self.sixieme.pk})
        self.assertContains(reponse, "a déjà un professeur, Lamour Test")
        self.assertFalse(Professeur.objects.filter(nom="Lafontant").exists())

        self.inscrire(self.primaire, "Lafontant", "3712 0002", **{"aff-classe": self.sixieme.pk, "aff-remplacer": "on"})
        nouveau = Professeur.objects.get(nom="Lafontant")
        self.assertEqual(nouveau.affectation_active.classe, self.sixieme)
        self.assertIsNone(ancien.affectation_active)
        self.assertEqual(list(ancien.classes.all()), [])

    def test_secondaire_cours_et_conflits(self):
        h1, h2 = self.heures[0], self.heures[1]
        reponse = self.inscrire(self.secondaire, "Pierre", "3712 0001", matiere_principale="Mathématiques",
                                **self.lignes_de_cours(("Mathématiques", self.septieme, 1, h1), ("Mathématiques", self.nsi, 3, h2)))
        pierre = Professeur.objects.get(nom="Pierre")
        self.assertRedirects(reponse, reverse("core:professeur_acces", args=[pierre.pk]), fetch_redirect_response=False)
        self.assertEqual(pierre.cours.count(), 2)
        self.assertEqual(set(pierre.cours.values_list("statut", flat=True)), {choices.STATUT_COURS_PROPOSE})
        self.assertEqual(set(pierre.classes.all()), {self.septieme, self.nsi})

        # La 7ème AF est déjà prise le lundi en 1re heure
        reponse = self.inscrire(self.secondaire, "Blaise", "3712 0002",
                                **self.lignes_de_cours(("Informatique", self.septieme, 1, h1)))
        self.assertContains(reponse, "La classe 7ème AF a déjà un cours le lundi en 1re heure : Mathématiques avec Pierre Test.")
        # Deux cours du même professeur à la même heure
        reponse = self.inscrire(self.secondaire, "Blaise", "3712 0002",
                                **self.lignes_de_cours(("Informatique", self.septieme, 2, h1), ("Informatique", self.nsi, 2, h1)))
        self.assertContains(reponse, "Deux cours du professeur tombent le mardi en 1re heure.")
        # Aucune ligne remplie
        reponse = self.inscrire(self.secondaire, "Blaise", "3712 0002", **self.lignes_de_cours())
        self.assertContains(reponse, "Ajoutez au moins un cours.")
        self.assertFalse(Professeur.objects.filter(nom="Blaise").exists())

    def test_telephone_deja_utilise(self):
        reponse = self.inscrire(self.primaire, "Double", "+509 3712-0000", **{"aff-classe": self.sixieme.pk})
        self.assertRedirects(reponse, reverse("core:professeur_acces", args=[Professeur.objects.get(nom="Double").pk]),
                             fetch_redirect_response=False)
        reponse = self.inscrire(self.kinder, "Encore", "37120000", **{"aff-classe": self.k2.pk, "aff-role": choices.ROLE_TITULAIRE})
        self.assertContains(reponse, "Ce numéro sert déjà d&#x27;identifiant à un autre compte.")

    def test_validation_par_la_direction_de_la_section(self):
        self.inscrire(self.secondaire, "Pierre", "3712 0001", **self.lignes_de_cours(("Mathématiques", self.nsi, 4, self.heures[2])))
        pierre = Professeur.objects.get(nom="Pierre")
        valider = reverse("core:professeur_valider_cours", args=[pierre.pk])

        # Ni la secrétaire ni la direction du primaire ne valident les cours du secondaire
        self.assertEqual(self.client.post(valider).status_code, 403)
        dir_pri = Utilisateur.objects.create_user("dirpri", password="x")
        Employe.objects.create(nom="Dir", prenom="Pri", poste="Directeur(trice) du primaire", section=self.primaire, utilisateur=dir_pri)
        self.client.force_login(dir_pri)
        self.assertEqual(self.client.post(valider).status_code, 403)

        # Le professeur ne voit son emploi du temps qu'après la validation
        pierre.utilisateur.doit_changer_mot_de_passe = False
        pierre.utilisateur.save()
        self.client.force_login(pierre.utilisateur)
        self.assertContains(self.client.get(reverse("core:espace")), "après sa validation")

        dir_sec = Utilisateur.objects.create_user("dirsec", password="x")
        Employe.objects.create(nom="Dorvil", prenom="Sec", poste="Directeur(trice) pédagogique du secondaire",
                               section=self.secondaire, utilisateur=dir_sec)
        self.client.force_login(dir_sec)
        self.assertContains(self.client.get(reverse("core:professeur_fiche", args=[pierre.pk])), "Valider les cours")
        self.assertRedirects(self.client.post(valider), reverse("core:professeur_fiche", args=[pierre.pk]))
        self.assertEqual(pierre.cours.get().statut, choices.STATUT_COURS_VALIDE)

        self.client.force_login(pierre.utilisateur)
        reponse = self.client.get(reverse("core:espace"))
        self.assertContains(reponse, "Mon emploi du temps")
        self.assertContains(reponse, "NSI")

    def test_seule_la_secretaire_inscrit(self):
        dir_sec = Utilisateur.objects.create_user("dirsec", password="x")
        Employe.objects.create(nom="Dorvil", prenom="Sec", poste="Directeur(trice) pédagogique du secondaire",
                               section=self.secondaire, utilisateur=dir_sec)
        self.client.force_login(dir_sec)
        self.assertEqual(self.client.get(reverse("core:professeur_creer")).status_code, 403)

    def test_retirer_un_cours_et_nouveau_mot_de_passe(self):
        self.inscrire(self.secondaire, "Pierre", "3712 0001", **self.lignes_de_cours(("Mathématiques", self.nsi, 4, self.heures[2])))
        pierre = Professeur.objects.get(nom="Pierre")
        self.client.post(reverse("core:cours_supprimer", args=[pierre.cours.get().pk]))
        self.assertEqual(pierre.cours.count(), 0)
        self.assertEqual(list(pierre.classes.all()), [])

        compte = pierre.utilisateur
        compte.doit_changer_mot_de_passe = False
        compte.save()
        reponse = self.client.post(reverse("core:professeur_nouveau_mot_de_passe", args=[pierre.pk]))
        self.assertRedirects(reponse, reverse("core:professeur_acces", args=[pierre.pk]), fetch_redirect_response=False)
        compte.refresh_from_db()
        self.assertTrue(compte.doit_changer_mot_de_passe)
        mot_de_passe = self.client.get(reverse("core:professeur_acces", args=[pierre.pk])).context["mot_de_passe"]
        self.assertTrue(compte.check_password(mot_de_passe))

    def test_changer_de_classe_au_primaire(self):
        cinquieme = Classe.objects.create(nom="5ème AF", section=self.primaire)
        self.inscrire(self.primaire, "Lamour", "3712 0001", **{"aff-classe": self.sixieme.pk})
        lamour = Professeur.objects.get(nom="Lamour")
        self.client.post(reverse("core:professeur_affecter", args=[lamour.pk]), {"classe": cinquieme.pk})
        self.assertEqual(lamour.affectation_active.classe, cinquieme)
        self.assertEqual(lamour.affectations.count(), 2)
        self.client.post(reverse("core:affectation_terminer", args=[lamour.affectation_active.pk]))
        self.assertIsNone(lamour.affectation_active)


class SaisieDesNotesTests(TestCase):
    """Les professeurs saisissent les notes de leurs classes, et seulement celles-là."""

    @classmethod
    def setUpTestData(cls):
        cls.primaire = Section.objects.get(nom=choices.SECTION_PRIMAIRE)
        cls.secondaire = Section.objects.get(nom=choices.SECTION_SECONDAIRE)
        cls.sixieme = Classe.objects.create(nom="6ème AF", section=cls.primaire)
        cls.septieme = Classe.objects.create(nom="7ème AF", section=cls.secondaire)
        cls.nsi = Classe.objects.create(nom="NSI", section=cls.secondaire)
        cls.anne = Eleve.objects.create(nom="Joseph", prenom="Anne", genre="Féminin", classe=cls.sixieme)
        cls.paul = Eleve.objects.create(nom="Louis", prenom="Paul", genre="Masculin", classe=cls.sixieme)
        cls.marc = Eleve.objects.create(nom="Pierre", prenom="Marc", genre="Masculin", classe=cls.septieme)
        cls.heure = Creneau.objects.filter(section=cls.secondaire, est_un_cours=True).first()

    def professeur(self, nom, section):
        compte = Utilisateur.objects.create_user(nom.lower(), password="x")
        return Professeur.objects.create(nom=nom, prenom="Test", section=section, utilisateur=compte)

    def choix(self, classe, matiere):
        return f"{classe.pk}:{matiere}"

    def test_primaire_toutes_les_matieres_de_sa_classe(self):
        prof = self.professeur("Blaise", self.primaire)
        Affectation.objects.create(professeur=prof, classe=self.sixieme)
        self.client.force_login(prof.utilisateur)
        page = self.client.get(reverse("core:saisie_notes"))
        self.assertContains(page, "6ème AF · Mathématiques")
        self.assertNotContains(page, "7ème AF")

        choix = self.choix(self.sixieme, "Mathématiques")
        page = self.client.get(reverse("core:saisie_notes"), {"choix": choix, "periode": "2e Trimestre"})
        self.assertContains(page, "Joseph Anne")
        self.assertContains(page, "Louis Paul")
        self.assertNotContains(page, "Pierre Marc")

        reponse = self.client.post(reverse("core:saisie_notes"), {
            "choix": choix, "periode": "2e Trimestre", f"note_{self.anne.pk}": "72,5", f"note_{self.paul.pk}": "",
        })
        # Après l'enregistrement, le professeur arrive sur « Mes notes », sur le groupe enregistré
        ancre = f"g-{self.sixieme.pk}-mathematiques"
        self.assertRedirects(reponse, f"{reverse('core:mes_notes')}#{ancre}", fetch_redirect_response=False)
        # « Mes notes » : par classe, puis par matière, une colonne par trimestre, toute la classe
        page = self.client.get(reverse("core:mes_notes"))
        self.assertContains(page, f'id="{ancre}"')
        self.assertContains(page, "<h3>Mathématiques", html=False)
        self.assertContains(page, "<td>72,5</td>", html=False)
        self.assertContains(page, "Louis Paul")
        note = Note.objects.get()
        self.assertEqual((note.eleve, note.matiere, note.periode, note.professeur), (self.anne, "Mathématiques", "2e Trimestre", prof))
        self.assertEqual(float(note.note), 72.5)
        self.assertEqual(note.annee_scolaire, choices.annee_scolaire_courante())

        # La page affiche la note ; la changer met à jour la même ligne, la vider la retire
        page = self.client.get(reverse("core:saisie_notes"), {"choix": choix, "periode": "2e Trimestre"})
        self.assertContains(page, 'value="72,5"')
        self.client.post(reverse("core:saisie_notes"), {"choix": choix, "periode": "2e Trimestre", f"note_{self.anne.pk}": "80"})
        self.assertEqual(Note.objects.get().note, 80)
        self.client.post(reverse("core:saisie_notes"), {"choix": choix, "periode": "2e Trimestre", f"note_{self.anne.pk}": ""})
        self.assertFalse(Note.objects.exists())

    def test_note_invalide_rien_n_est_enregistre(self):
        prof = self.professeur("Blaise", self.primaire)
        Affectation.objects.create(professeur=prof, classe=self.sixieme)
        self.client.force_login(prof.utilisateur)
        reponse = self.client.post(reverse("core:saisie_notes"), {
            "choix": self.choix(self.sixieme, "Français"), "periode": "1er Trimestre",
            f"note_{self.anne.pk}": "85", f"note_{self.paul.pk}": "120",
        })
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "La note doit être comprise entre 0 et 100.")
        self.assertContains(reponse, 'value="120"')
        self.assertFalse(Note.objects.exists())

    def test_secondaire_seulement_les_cours_valides(self):
        prof = self.professeur("Durand", self.secondaire)
        Cours.objects.create(professeur=prof, classe=self.septieme, matiere="Anglais", jour=1, creneau=self.heure,
                             statut=choices.STATUT_COURS_VALIDE, annee_scolaire=choices.annee_scolaire_courante())
        Cours.objects.create(professeur=prof, classe=self.nsi, matiere="Anglais", jour=2, creneau=self.heure,
                             statut=choices.STATUT_COURS_PROPOSE, annee_scolaire=choices.annee_scolaire_courante())
        self.client.force_login(prof.utilisateur)
        page = self.client.get(reverse("core:saisie_notes"))
        # Un seul choix : la grille s'ouvre directement
        self.assertContains(page, "7ème AF · Anglais")
        self.assertContains(page, "Pierre Marc")
        self.assertNotContains(page, "NSI")
        for choix in [self.choix(self.nsi, "Anglais"), self.choix(self.septieme, "Français"), self.choix(self.sixieme, "Anglais")]:
            with self.subTest(choix=choix):
                reponse = self.client.post(reverse("core:saisie_notes"), {"choix": choix, "periode": "1er Trimestre",
                                                                          f"note_{self.marc.pk}": "50"})
                self.assertEqual(reponse.status_code, 403)
        self.assertFalse(Note.objects.exists())

    def test_sans_classe_rien_a_noter_et_menu(self):
        prof = self.professeur("Blaise", self.primaire)
        self.client.force_login(prof.utilisateur)
        page = self.client.get(reverse("core:saisie_notes"))
        self.assertContains(page, "pas encore de classe à noter")
        self.assertContains(page, reverse("core:saisie_notes"))  # lien du menu

    def test_personnel_sans_fiche_professeur_refuse(self):
        compte = Utilisateur.objects.create_user("sec", password="x")
        Employe.objects.create(nom="Auguste", prenom="Nadège", poste="Secrétaire", utilisateur=compte)
        self.client.force_login(compte)
        self.assertEqual(self.client.get(reverse("core:saisie_notes")).status_code, 403)
        self.assertNotContains(self.client.get(reverse("core:dashboard")), reverse("core:saisie_notes"))


class AnniversairesTests(TestCase):
    """Dates de naissance et d'embauche : alertes du tableau de bord et message de bienvenue."""

    def setUp(self):
        from datetime import date
        self.date = date
        self.jour = date(2026, 9, 26)

    def test_evenements_des_7_prochains_jours(self):
        from . import anniversaires
        d = self.date
        gens = [
            Professeur(nom="Blaise", prenom="Rose", date_naissance=d(1990, 9, 26)),            # aujourd'hui
            Employe(nom="Jean", prenom="Luc", poste="Censeur", date_naissance=d(1985, 9, 29),    # dans 3 jours
                    date_embauche=d(2016, 10, 3)),                                            # 10 ans dans 7 jours
            Professeur(nom="Noël", prenom="Ana", date_naissance=d(1980, 10, 4)),                # dans 8 jours : non
            Professeur(nom="Neuf", prenom="Eva", date_embauche=d(2026, 9, 26)),                 # arrivée aujourd'hui : non
        ]
        evenements = anniversaires.evenements(gens, le=self.jour)
        self.assertEqual([(e.personne.nom, e.genre, e.dans, e.annees) for e in evenements], [
            ("Blaise", "naissance", 0, 36), ("Jean", "naissance", 3, 41), ("Jean", "embauche", 7, 10),
        ])
        self.assertEqual(evenements[0].quand, "Aujourd'hui")
        self.assertEqual(evenements[1].fonction, "Censeur")
        self.assertEqual(evenements[2].texte, "Luc Jean : 10 ans à l'école")

    def test_ne_le_29_fevrier(self):
        from . import anniversaires
        d = self.date
        self.assertEqual(anniversaires.prochaine_date(d(2000, 2, 29), d(2027, 2, 20)), d(2027, 2, 28))
        self.assertEqual(anniversaires.prochaine_date(d(2000, 2, 29), d(2028, 2, 20)), d(2028, 2, 29))
        self.assertEqual(anniversaires.prochaine_date(d(1990, 1, 5), d(2026, 9, 26)), d(2027, 1, 5))

    def test_tableau_de_bord_et_bienvenue(self):
        from django.utils import timezone
        aujourd_hui = timezone.localdate()
        primaire = Section.objects.get(nom=choices.SECTION_PRIMAIRE)
        secondaire = Section.objects.get(nom=choices.SECTION_SECONDAIRE)
        Professeur.objects.create(nom="Blaise", prenom="Rose", section=primaire,
                                  date_naissance=aujourd_hui.replace(year=1990) if aujourd_hui.month != 2 or aujourd_hui.day != 29 else aujourd_hui)
        Professeur.objects.create(nom="Autre", prenom="Section", section=secondaire,
                                  date_naissance=aujourd_hui.replace(year=1991) if aujourd_hui.month != 2 or aujourd_hui.day != 29 else aujourd_hui)
        compte = Utilisateur.objects.create_user("dirpri", password="Motdepasse-2026", first_name="Marie")
        Employe.objects.create(nom="Jean", prenom="Marie", poste="Directeur(trice) du primaire", section=primaire,
                               utilisateur=compte)

        reponse = self.client.post(reverse("core:login"), {"username": "dirpri", "password": "Motdepasse-2026"}, follow=True)
        self.assertContains(reponse, "Bienvenue, Marie !")
        self.assertContains(reponse, "Aujourd&#x27;hui, c&#x27;est l&#x27;anniversaire de Rose Blaise.")
        self.assertContains(reponse, '<dialog class="bienvenue"')
        # Le tableau de bord ne montre que la section de la direction
        self.assertContains(reponse, "Anniversaire de Rose Blaise")
        self.assertNotContains(reponse, "Section Autre")
        # La fenêtre ne s'ouvre qu'une fois
        self.assertNotContains(self.client.get(reverse("core:dashboard")), '<dialog class="bienvenue"')

    def test_le_professeur_recoit_ses_voeux(self):
        from django.utils import timezone
        aujourd_hui = timezone.localdate()
        if (aujourd_hui.month, aujourd_hui.day) == (2, 29):
            self.skipTest("29 février")
        compte = Utilisateur.objects.create_user("rose", password="x")
        prof = Professeur.objects.create(nom="Blaise", prenom="Rose", utilisateur=compte,
                                         date_naissance=aujourd_hui.replace(year=1990),
                                         date_embauche=aujourd_hui.replace(year=aujourd_hui.year - 5))
        self.assertEqual((prof.age, prof.anciennete), (aujourd_hui.year - 1990, 5))
        self.client.force_login(compte)
        self.assertContains(self.client.get(reverse("core:espace")), "Joyeux anniversaire, Rose !")


class IconesTests(TestCase):
    def test_plus_aucun_emoji_dans_les_pages(self):
        import re
        from pathlib import Path
        from django.conf import settings
        emoji = re.compile("[\U0001F300-\U0001FAFF☀-➿️]")
        for fichier in Path(settings.BASE_DIR, "templates").rglob("*.html"):
            with self.subTest(fichier=fichier.name):
                self.assertIsNone(emoji.search(fichier.read_text(encoding="utf-8")))

    def test_les_icones_existent_dans_le_fichier_svg(self):
        import re
        from pathlib import Path
        from django.conf import settings
        svg = Path(settings.BASE_DIR, "static", "icones", "icones.svg").read_text(encoding="utf-8")
        disponibles = set(re.findall(r'<symbol id="([^"]+)"', svg))
        utilisees = set()
        for fichier in Path(settings.BASE_DIR, "templates").rglob("*.html"):
            utilisees |= set(re.findall(r'{% icone "([^"]+)"', fichier.read_text(encoding="utf-8")))
        for fichier in Path(settings.BASE_DIR, "core").glob("views*.py"):
            utilisees |= set(re.findall(r'"icone_titre": "([^"]+)"', fichier.read_text(encoding="utf-8")))
        self.assertTrue(utilisees)
        self.assertEqual(utilisees - disponibles, set())


class NotesVisiblesTests(TestCase):
    """Une note saisie par un professeur apparaît dans « Mes notes » et chez la secrétaire."""

    @classmethod
    def setUpTestData(cls):
        primaire = Section.objects.get(nom=choices.SECTION_PRIMAIRE)
        cls.sixieme = Classe.objects.create(nom="6ème AF", section=primaire)
        cls.cinquieme = Classe.objects.create(nom="5ème AF", section=primaire)
        cls.anne = Eleve.objects.create(nom="Joseph", prenom="Anne", genre="Féminin", classe=cls.sixieme)
        cls.luc = Eleve.objects.create(nom="Noël", prenom="Luc", genre="Masculin", classe=cls.cinquieme)
        cls.prof = Professeur.objects.create(nom="Blaise", prenom="Rose", section=primaire,
                                             utilisateur=Utilisateur.objects.create_user("rose", password="x"))
        Affectation.objects.create(professeur=cls.prof, classe=cls.sixieme)
        autre = Professeur.objects.create(nom="Autre", prenom="Prof", section=primaire)
        annee = choices.annee_scolaire_courante()
        Note.objects.create(eleve=cls.luc, professeur=autre, matiere="Français", note=55, periode="1er Trimestre",
                            annee_scolaire=annee)

    def test_le_professeur_ne_voit_que_ses_notes(self):
        self.client.force_login(self.prof.utilisateur)
        self.client.post(reverse("core:saisie_notes"), {"choix": f"{self.sixieme.pk}:Français", "periode": "1er Trimestre",
                                                        f"note_{self.anne.pk}": "91"})
        page = self.client.get(reverse("core:mes_notes"))
        self.assertContains(page, "Joseph Anne")
        self.assertNotContains(page, "Noël Luc")
        self.assertContains(page, reverse("core:saisie_notes"))  # bouton Modifier vers la grille
        espace = self.client.get(reverse("core:espace"))
        self.assertContains(espace, "Vous avez saisi <strong>1</strong> note cette année.", html=False)
        self.assertContains(espace, reverse("core:mes_notes"))

    def test_la_secretaire_voit_les_notes_saisies(self):
        Note.objects.create(eleve=self.anne, professeur=self.prof, matiere="Français", note=91, periode="2e Trimestre",
                            annee_scolaire=choices.annee_scolaire_courante())
        compte = Utilisateur.objects.create_user("sec", password="x")
        Employe.objects.create(nom="Jean", prenom="Marie", poste="Secrétaire", utilisateur=compte)
        self.client.force_login(compte)
        tableau = self.client.get(reverse("core:dashboard"))
        self.assertContains(tableau, "Dernières notes saisies")
        self.assertContains(tableau, "Joseph Anne : 91/100")
        liste = self.client.get(reverse("core:note_liste"), {"classe": self.sixieme.pk})
        self.assertContains(liste, "Joseph Anne")
        self.assertNotContains(liste, "Noël Luc")
        # Par classe, puis par matière
        liste = self.client.get(reverse("core:note_liste"))
        self.assertEqual([g["classe"] for g in liste.context["classes_notes"]], [self.cinquieme, self.sixieme])
        self.assertEqual([m["matiere"] for m in liste.context["classes_notes"][1]["matieres"]], ["Français"])
        ligne = liste.context["classes_notes"][1]["matieres"][0]["lignes"][0]
        self.assertEqual([n.note if n else None for n in ligne["cellules"]], [None, 91, None])
        liste = self.client.get(reverse("core:note_liste"), {"q": "Blaise"})
        self.assertContains(liste, "Joseph Anne")
        self.assertNotContains(liste, "Noël Luc")
        self.assertEqual(self.client.get(reverse("core:mes_notes")).status_code, 403)

    def test_comptes_d_essai(self):
        from django.core.management import call_command
        from io import StringIO
        with self.settings(DEBUG=True):
            call_command("seed_data", stdout=StringIO())
        secretaire = Utilisateur.objects.get(username="secretaire")
        self.assertTrue(secretaire.check_password("secretaire123"))
        self.assertEqual(roles.roles_de(secretaire), {roles.SECRETARIAT})
        self.assertEqual(roles.roles_de(Utilisateur.objects.get(username="prof")), {roles.PROFESSEUR})
        direction = Utilisateur.objects.get(username="direction")
        self.assertEqual(roles.roles_de(direction), {roles.DIRECTION_SECTION})
        self.assertEqual(roles.section_de(direction).nom, choices.SECTION_PRIMAIRE)
        parent = Utilisateur.objects.get(username="parent")
        self.assertTrue(parent.check_password("parent123"))
        self.assertEqual(roles.roles_de(parent), {roles.PARENT})
        self.assertEqual([str(e) for e in parent.parent.enfants.all()], ["Martin Marie"])


class PhotosEtFichesTests(TestCase):
    """Photos (réduites, protégées) et fiches d'un élève, d'une classe et d'un employé."""

    @classmethod
    def setUpTestData(cls):
        cls.primaire = Section.objects.get(nom=choices.SECTION_PRIMAIRE)
        cls.secondaire = Section.objects.get(nom=choices.SECTION_SECONDAIRE)
        cls.sixieme = Classe.objects.create(nom="6ème AF", section=cls.primaire)
        cls.septieme = Classe.objects.create(nom="7ème AF", section=cls.secondaire)
        cls.anne = Eleve.objects.create(nom="Joseph", prenom="Anne", genre="Féminin", classe=cls.sixieme)
        cls.marc = Eleve.objects.create(nom="Pierre", prenom="Marc", genre="Masculin", classe=cls.septieme)

    def setUp(self):
        import tempfile
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        reglage = self.settings(MEDIA_ROOT=dossier.name)
        reglage.enable()
        self.addCleanup(reglage.disable)
        self.secretaire = Utilisateur.objects.create_user("sec", password="x")
        Employe.objects.create(nom="Jean", prenom="Marie", poste="Secrétaire", utilisateur=self.secretaire)

    def image(self, largeur=2000, hauteur=1500, nom="photo.png"):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        tampon = BytesIO()
        Image.new("RGB", (largeur, hauteur), (30, 60, 140)).save(tampon, "PNG")
        return SimpleUploadedFile(nom, tampon.getvalue(), content_type="image/png")

    def test_photo_reduite_et_protegee(self):
        from PIL import Image
        self.client.force_login(self.secretaire)
        reponse = self.client.post(reverse("core:eleve_modifier", args=[self.anne.pk]), {
            "photo": self.image(), "nom": "Joseph", "prenom": "Anne", "genre": "Féminin", "classe": self.sixieme.pk,
        })
        self.assertRedirects(reponse, reverse("core:eleve_fiche", args=[self.anne.pk]))
        self.anne.refresh_from_db()
        self.assertRegex(self.anne.photo.name, r"^photos/eleve/[0-9a-f]{32}\.jpg$")
        with self.anne.photo.open("rb") as f:
            self.assertEqual(max(Image.open(f).size), 800)
        url = reverse("core:photo", args=["eleve", self.anne.pk])
        self.assertContains(self.client.get(reverse("core:eleve_liste")), url)
        reponse = self.client.get(url)
        self.assertEqual((reponse.status_code, reponse["Content-Type"]), (200, "image/jpeg"))

        # Sans droit sur l'élève : rien (un parent, un professeur d'une autre classe)
        parent = Utilisateur.objects.create_user("parent", password="x")
        parent.groups.add(Group.objects.get(name=roles.PARENT))
        self.client.force_login(parent)
        self.assertEqual(self.client.get(url).status_code, 404)
        prof = Professeur.objects.create(nom="Blaise", prenom="Rose", section=self.primaire,
                                         utilisateur=Utilisateur.objects.create_user("rose", password="x"))
        self.client.force_login(prof.utilisateur)
        self.assertEqual(self.client.get(url).status_code, 404)
        # Le professeur de la classe la voit
        Affectation.objects.create(professeur=prof, classe=self.sixieme)
        prof.classes.add(self.sixieme)
        self.assertEqual(self.client.get(url).status_code, 200)

        # Une nouvelle photo remplace l'ancienne sur le disque, et la fiche supprimée l'emporte
        ancienne = self.anne.photo.name
        self.client.force_login(self.secretaire)
        self.client.post(reverse("core:eleve_modifier", args=[self.anne.pk]), {
            "photo": self.image(300, 400), "nom": "Joseph", "prenom": "Anne", "genre": "Féminin", "classe": self.sixieme.pk,
        })
        self.anne.refresh_from_db()
        stockage = self.anne.photo.storage
        self.assertFalse(stockage.exists(ancienne))
        nouvelle = self.anne.photo.name
        with self.captureOnCommitCallbacks(execute=True):
            self.anne.delete()
        self.assertFalse(stockage.exists(nouvelle))

    def test_photo_trop_lourde_ou_illisible(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.secretaire)
        donnees = {"nom": "Noël", "prenom": "Luc", "genre": "Masculin", "classe": self.sixieme.pk}
        faux = SimpleUploadedFile("photo.jpg", b"pas une image", content_type="image/jpeg")
        reponse = self.client.post(reverse("core:eleve_creer"), {**donnees, "photo": faux})
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Eleve.objects.filter(nom="Noël").exists())
        from . import photos
        with self.settings():
            ancien, photos.TAILLE_MAX = photos.TAILLE_MAX, 100
            try:
                reponse = self.client.post(reverse("core:eleve_creer"), {**donnees, "photo": self.image(50, 50)})
            finally:
                photos.TAILLE_MAX = ancien
        self.assertContains(reponse, "La photo est trop lourde")

    def test_fiche_de_la_classe_avec_ses_eleves(self):
        self.client.force_login(self.secretaire)
        self.assertContains(self.client.get(reverse("core:classe_liste")), reverse("core:classe_fiche", args=[self.sixieme.pk]))
        page = self.client.get(reverse("core:classe_fiche", args=[self.sixieme.pk]))
        self.assertContains(page, "Joseph")
        self.assertNotContains(page, "Pierre")
        self.assertContains(page, f"?classe={self.sixieme.pk}")
        formulaire = self.client.get(reverse("core:eleve_creer"), {"classe": self.sixieme.pk}).context["form"]
        self.assertEqual(str(formulaire["classe"].value()), str(self.sixieme.pk))
        # Une direction ne voit que les classes de sa section
        direction = Utilisateur.objects.create_user("dir", password="x")
        Employe.objects.create(nom="Dir", prenom="Pri", poste="Directeur(trice) du primaire", section=self.primaire,
                               utilisateur=direction)
        self.client.force_login(direction)
        self.assertEqual(self.client.get(reverse("core:classe_fiche", args=[self.septieme.pk])).status_code, 404)

    def test_fiche_employe_sans_salaire_pour_la_direction(self):
        from datetime import date
        surveillant = Employe.objects.create(nom="Surv", prenom="Paul", poste="Surveillant(e)", section=self.primaire,
                                             salaire=12345, date_naissance=date(1990, 1, 5), adresse="Rue Capitale")
        direction = Utilisateur.objects.create_user("dir", password="x")
        Employe.objects.create(nom="Dir", prenom="Pri", poste="Directeur(trice) du primaire", section=self.primaire,
                               utilisateur=direction)
        self.client.force_login(direction)
        self.assertContains(self.client.get(reverse("core:employe_liste")), reverse("core:employe_fiche", args=[surveillant.pk]))
        page = self.client.get(reverse("core:employe_fiche", args=[surveillant.pk]))
        self.assertContains(page, "Rue Capitale")
        self.assertContains(page, "05/01/1990")
        self.assertNotContains(page, "12345")
        self.assertNotContains(page, "Jean")  # seulement ses informations à lui
        chef = Utilisateur.objects.create_user("chef", password="x")
        Employe.objects.create(nom="Chef", prenom="Dir", poste="Directeur(trice) en chef", utilisateur=chef)
        self.client.force_login(chef)
        self.assertContains(self.client.get(reverse("core:employe_fiche", args=[surveillant.pk])), "12345")

    def test_fiche_eleve_avec_ses_notes(self):
        Note.objects.create(eleve=self.anne, matiere="Français", note=77, periode="1er Trimestre",
                            annee_scolaire=choices.annee_scolaire_courante())
        self.client.force_login(self.secretaire)
        page = self.client.get(reverse("core:eleve_fiche", args=[self.anne.pk]))
        self.assertContains(page, "<h3>Français", html=False)
        self.assertContains(page, "<td>77</td>", html=False)
