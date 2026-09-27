# core/tests_activites.py
# Activités et concours (Génies en herbe...) : le secrétariat les publie avec
# leurs photos, tout le monde les voit sur la page « Activités » du site.
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from .models import Activite, PhotoActivite
from .tests_vie_scolaire import AvecUneEcole


def image(largeur=3000, hauteur=2000, nom="concours.png"):
    tampon = BytesIO()
    Image.new("RGB", (largeur, hauteur), (194, 65, 109)).save(tampon, "PNG")
    return SimpleUploadedFile(nom, tampon.getvalue(), content_type="image/png")


def taille(champ):
    with champ.open("rb") as f:
        return Image.open(f).size


class ActivitesTests(AvecUneEcole):
    def setUp(self):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        reglage = self.settings(MEDIA_ROOT=dossier.name)
        reglage.enable()
        self.addCleanup(reglage.disable)

    def publier(self, titre="Génies en herbe : la 7ème AF gagne la finale", photos=(), publiee=True, **autres):
        donnees = {"titre": titre, "categorie": "Génies en herbe", "date": "2026-09-20",
                   "texte": "Bravo aux quatre élèves de l'équipe.", "photos": list(photos), **autres}
        if publiee:
            donnees["publiee"] = "on"
        return self.client.post(reverse("core:activite_creer"), donnees)

    def test_la_secretaire_publie_un_concours_avec_ses_photos(self):
        self.client.force_login(self.secretaire)
        self.assertContains(self.client.get(reverse("core:dashboard")), reverse("core:activite_liste"))
        reponse = self.publier(photos=[image(nom="a.png"), image(1200, 1600, "b.png")])
        activite = Activite.objects.get()
        self.assertRedirects(reponse, reverse("core:activite_modifier", args=[activite.pk]))
        self.assertEqual(activite.cree_par, self.secretaire)
        grande, portrait = activite.photos.all()
        # Réduites pour le site, en JPEG, avec une vignette pour les listes
        self.assertEqual(taille(grande.image), (1600, 1067))
        self.assertEqual(taille(grande.vignette), (600, 400))
        self.assertEqual(taille(portrait.image), (1200, 1600))
        self.assertRegex(grande.image.name, r"^activites/[0-9a-f]{32}\.jpg$")

        # Une photo de plus depuis la page de l'activité (sans recréer les autres)
        self.client.post(reverse("core:activite_modifier", args=[activite.pk]), {
            "titre": activite.titre, "categorie": activite.categorie, "date": "2026-09-20", "texte": activite.texte, "publiee": "on",
            "photos": [image(nom="c.png")]})
        self.assertEqual(activite.photos.count(), 3)

        # Sur le site, pour tout le monde
        self.client.logout()
        for page in ("site:accueil", "site:activites"):
            # Espace insécable avant « : » : pas de retour à la ligne devant les deux-points
            self.assertContains(self.client.get(reverse(page)), "Génies en herbe\u00a0: la 7ème AF gagne la finale")
        detail = self.client.get(reverse("site:activite", args=[activite.pk]))
        self.assertContains(detail, "Bravo aux quatre élèves")
        self.assertContains(detail, reverse("site:photo_activite", args=[portrait.pk, "grande"]))
        photo = self.client.get(reverse("site:photo_activite", args=[grande.pk, "vignette"]))
        self.assertEqual((photo.status_code, photo["Content-Type"]), (200, "image/jpeg"))
        self.assertIn("public", photo["Cache-Control"])
        self.assertEqual(self.client.get(reverse("site:photo_activite", args=[grande.pk, "originale"])).status_code, 404)

        # Une photo retirée, puis l'activité supprimée : les fichiers partent du disque
        self.client.force_login(self.secretaire)
        stockage, fichiers = grande.image.storage, [grande.image.name, grande.vignette.name]
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("core:activite_photo_supprimer", args=[grande.pk]))
        self.assertFalse(any(stockage.exists(f) for f in fichiers))
        restants = [n for p in activite.photos.all() for n in (p.image.name, p.vignette.name)]
        self.assertEqual(len(restants), 4)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("core:activite_supprimer", args=[activite.pk]))
        self.assertFalse(Activite.objects.exists())
        self.assertFalse(PhotoActivite.objects.exists())
        self.assertFalse(any(stockage.exists(f) for f in restants))

    def test_une_activite_cachee_n_est_pas_sur_le_site(self):
        self.client.force_login(self.secretaire)
        self.publier("Sortie au musée", photos=[image()], publiee=False)
        activite, photo = Activite.objects.get(), PhotoActivite.objects.get()
        self.assertFalse(activite.publiee)
        url_photo = reverse("site:photo_activite", args=[photo.pk, "vignette"])
        # La secrétaire la voit encore dans la gestion
        self.assertContains(self.client.get(reverse("core:activite_liste")), "pas sur le site")
        self.assertEqual(self.client.get(url_photo)["Cache-Control"], "private, no-store")
        for compte in (None, self.parent):
            if compte:
                self.client.force_login(compte)
            else:
                self.client.logout()
            self.assertNotContains(self.client.get(reverse("site:activites")), "Sortie au musée")
            self.assertEqual(self.client.get(reverse("site:activite", args=[activite.pk])).status_code, 404)
            self.assertEqual(self.client.get(url_photo).status_code, 404)

    def test_seul_le_secretariat_gere_les_activites(self):
        for compte in (self.parent, self.prof, self.censeur, self.dir_primaire):
            self.client.force_login(compte)
            self.assertEqual(self.client.get(reverse("core:activite_liste")).status_code, 403)
            self.assertEqual(self.publier().status_code, 403)
        self.assertFalse(Activite.objects.exists())
        self.client.logout()
        self.assertEqual(self.client.get(reverse("core:activite_creer")).status_code, 302)

    def test_photo_illisible_ou_trop_lourde(self):
        from . import photos
        self.client.force_login(self.secretaire)
        faux = SimpleUploadedFile("finale.jpg", b"pas une image", content_type="image/jpeg")
        self.assertContains(self.publier(photos=[image(), faux]), "« finale.jpg » n&#x27;est pas une photo lisible")
        ancien, photos.TAILLE_MAX_ACTIVITE = photos.TAILLE_MAX_ACTIVITE, 100
        try:
            self.assertContains(self.publier(photos=[image(50, 50, "lourde.png")]), "« lourde.png » est trop lourde")
        finally:
            photos.TAILLE_MAX_ACTIVITE = ancien
        self.assertFalse(Activite.objects.exists())

    def test_filtrer_par_type_d_activite(self):
        Activite.objects.create(titre="Finale Génies en herbe", categorie="Génies en herbe")
        Activite.objects.create(titre="Fête de Noël", categorie="Fête")
        page = self.client.get(reverse("site:activites"), {"type": "Fête"})
        self.assertContains(page, "Fête de Noël")
        self.assertNotContains(page, "Finale Génies en herbe")
        # Un type inconnu : toutes les activités
        page = self.client.get(reverse("site:activites"), {"type": "rien"})
        self.assertContains(page, "Fête de Noël")
        self.assertContains(page, "Finale Génies en herbe")
