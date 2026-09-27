# core/anniversaires.py
# Anniversaires (date de naissance) et années passées à l'école (date
# d'embauche) des professeurs et des employés, pour les alertes du tableau
# de bord et le message de bienvenue.
from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone

JOURS_D_AVANCE = 7

NAISSANCE = "naissance"
EMBAUCHE = "embauche"


@dataclass
class Evenement:
    personne: object
    genre: str          # NAISSANCE ou EMBAUCHE
    jour: date          # prochaine date de l'anniversaire
    dans: int           # 0 = aujourd'hui
    annees: int         # âge atteint, ou années à l'école

    @property
    def aujourd_hui(self):
        return self.dans == 0

    @property
    def fonction(self):
        from .models import Professeur
        if isinstance(self.personne, Professeur):
            return "Professeur"
        return self.personne.poste or "Employé"

    @property
    def texte(self):
        if self.genre == NAISSANCE:
            return f"Anniversaire de {self.personne.prenom} {self.personne.nom} ({self.annees} ans)"
        s = "s" if self.annees > 1 else ""
        return f"{self.personne.prenom} {self.personne.nom} : {self.annees} an{s} à l'école"

    @property
    def quand(self):
        if self.dans == 0:
            return "Aujourd'hui"
        if self.dans == 1:
            return "Demain"
        return f"Dans {self.dans} jours"


def aujourd_hui():
    return timezone.localdate()


def prochaine_date(origine, depuis):
    """Prochain anniversaire d'une date à partir de `depuis` (le 29 février tombe le 28 les autres années)."""
    for annee in (depuis.year, depuis.year + 1):
        try:
            jour = origine.replace(year=annee)
        except ValueError:
            jour = date(annee, 2, 28)
        if jour >= depuis:
            return jour
    return None


def age(naissance, le=None):
    le = le or aujourd_hui()
    return le.year - naissance.year - ((le.month, le.day) < (naissance.month, naissance.day))


def evenements(personnes, jours=JOURS_D_AVANCE, le=None):
    """Anniversaires et années à l'école dans les `jours` qui viennent, du plus proche au plus lointain."""
    le = le or aujourd_hui()
    limite = le + timedelta(days=jours)
    resultat = []
    for personne in personnes:
        for genre, origine in ((NAISSANCE, personne.date_naissance), (EMBAUCHE, personne.date_embauche)):
            if origine is None:
                continue
            jour = prochaine_date(origine, le)
            annees = jour.year - origine.year
            # Pas d'alerte le jour même de l'arrivée à l'école
            if jour > limite or annees < 1:
                continue
            resultat.append(Evenement(personne, genre, jour, (jour - le).days, annees))
    resultat.sort(key=lambda e: (e.dans, e.genre != NAISSANCE, e.personne.nom))
    return resultat


def anniversaires_du_jour(personnes, le=None):
    """Seulement les anniversaires de naissance d'aujourd'hui."""
    return [e for e in evenements(personnes, jours=0, le=le) if e.genre == NAISSANCE]


def personnel_visible(user):
    """Professeurs et employés que l'utilisateur a le droit de voir (selon son rôle et sa section)."""
    from . import roles
    from .models import Employe, Professeur

    personnes = []
    if roles.peut(user, "professeurs"):
        personnes += list(roles.filtrer(user, "professeurs", Professeur.objects.all()))
    if roles.peut(user, "employes"):
        personnes += list(roles.filtrer(user, "employes", Employe.objects.all()))
    return personnes


def fiche_de(user):
    """Fiche professeur ou employé du compte connecté, ou None."""
    for nom in ("professeur", "employe"):
        fiche = getattr(user, nom, None)
        if fiche is not None:
            return fiche
    return None


def c_est_sa_fete(fiche, le=None):
    return bool(fiche and fiche.date_naissance and anniversaires_du_jour([fiche], le=le))


def prenom_de(user):
    fiche = fiche_de(user)
    return user.first_name or (fiche.prenom if fiche else "") or user.get_username()


def message_de_bienvenue(user):
    """Texte de la petite fenêtre qui s'ouvre juste après la connexion."""
    from django.utils.formats import date_format

    prenom = prenom_de(user)
    lignes = [f"Bienvenue, {prenom} !", f"Nous sommes le {date_format(aujourd_hui(), 'l j F Y')}."]
    if c_est_sa_fete(fiche_de(user)):
        lignes[0] = f"Joyeux anniversaire, {prenom} !"
        lignes.insert(1, "Toute l'équipe des Nénuphars vous souhaite une belle journée.")
    fetes = [e for e in anniversaires_du_jour(personnel_visible(user)) if e.personne != fiche_de(user)]
    if fetes:
        noms = [f"{e.personne.prenom} {e.personne.nom}" for e in fetes]
        liste = noms[0] if len(noms) == 1 else ", ".join(noms[:-1]) + " et " + noms[-1]
        lignes.append(f"Aujourd'hui, c'est l'anniversaire de {liste}.")
    parent = getattr(user, "parent", None)
    if parent is not None:
        from . import notifications
        nouveau = notifications.phrase(notifications.compte_par_categorie(parent))
        if nouveau:
            lignes.append(f"Nouveau pour vous : {nouveau}. Voyez le menu « Notifications ».")
    if user.doit_changer_mot_de_passe:
        lignes.append("Pour commencer, choisissez votre propre mot de passe.")
    return "\n".join(lignes)
