# core/tests.py
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from . import choices, roles
from .models import Affectation, Classe, Creneau, Eleve, Employe, Note, Paiement, Professeur, Section, Utilisateur
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
