# core/professeurs.py
# Règles du module professeurs (cahier des charges, section F) :
# - Kindergarten : une classe, deux maîtresses au plus, dont une seule titulaire ;
# - Primaire : une classe, un seul professeur par classe (le remplacer se confirme) ;
# - Secondaire : une ligne par cours, sans conflit d'horaire.
import secrets

from django.db.models import Q
from django.utils import timezone

from . import choices
from .models import Affectation, Cours, Utilisateur
from .telephone import normaliser_telephone

PLACES_KINDERGARTEN = 2

# Sans 0/O ni 1/I/L, pour qu'un mot de passe recopié à la main ne prête pas à confusion
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def mot_de_passe_provisoire():
    brut = "".join(secrets.choice(_ALPHABET) for _ in range(8))
    return f"{brut[:4]}-{brut[4:]}"


# ─────────────────────────── Comptes ───────────────────────────
def creer_compte(professeur):
    """Crée le compte du professeur (identifiant : son téléphone). Renvoie le mot de passe provisoire."""
    telephone = normaliser_telephone(professeur.telephone)
    identifiant = telephone
    if Utilisateur.objects.filter(username=identifiant).exists():
        identifiant = f"prof-{professeur.pk}"
    mot_de_passe = mot_de_passe_provisoire()
    compte = Utilisateur.objects.create_user(
        username=identifiant, password=mot_de_passe, telephone=telephone,
        first_name=professeur.prenom, last_name=professeur.nom, email=professeur.email or "",
        doit_changer_mot_de_passe=True,
    )
    professeur.utilisateur = compte
    professeur.save()
    return mot_de_passe


def nouveau_mot_de_passe(compte):
    mot_de_passe = mot_de_passe_provisoire()
    compte.set_password(mot_de_passe)
    compte.doit_changer_mot_de_passe = True
    compte.save()
    return mot_de_passe


def mettre_a_jour_compte(professeur):
    """Après une modification de la fiche : nom, e-mail et téléphone du compte suivent."""
    compte = professeur.utilisateur
    if compte is None:
        return
    compte.first_name, compte.last_name = professeur.prenom, professeur.nom
    compte.email = professeur.email or ""
    compte.telephone = normaliser_telephone(professeur.telephone) or None
    compte.save()


def telephone_deja_utilise(telephone, compte_actuel=None):
    numero = normaliser_telephone(telephone)
    comptes = Utilisateur.objects.filter(telephone=numero)
    if compte_actuel is not None:
        comptes = comptes.exclude(pk=compte_actuel.pk)
    return comptes.exists()


# ─────────────────────── Kindergarten et primaire ───────────────────────
def affectations_actives(classe, sauf=None):
    actives = classe.affectations.filter(date_fin__isnull=True).select_related("professeur")
    if sauf is not None and sauf.pk:
        actives = actives.exclude(professeur=sauf)
    return list(actives)


def description_classe(classe, section, sauf=None):
    """Texte de la liste déroulante : qui est déjà dans la classe."""
    actives = affectations_actives(classe, sauf)
    if section.est_primaire:
        return f"{classe.nom} · {actives[0].professeur}" if actives else f"{classe.nom} · sans professeur"
    libres = PLACES_KINDERGARTEN - len(actives)
    if libres <= 0:
        return f"{classe.nom} · complète"
    return f"{classe.nom} · {libres} place{'s' if libres > 1 else ''}"


def affecter(professeur, classe, role, remplacer=()):
    """Place le professeur dans la classe ; termine son affectation précédente et celles qu'il remplace."""
    aujourd_hui = timezone.localdate()
    remplaces = [a.professeur for a in remplacer]
    Affectation.objects.filter(Q(professeur=professeur) | Q(pk__in=[a.pk for a in remplacer]), date_fin__isnull=True) \
        .update(date_fin=aujourd_hui)
    affectation = Affectation.objects.create(professeur=professeur, classe=classe, role=role, date_debut=aujourd_hui)
    for autre in [professeur, *remplaces]:
        synchroniser_classes(autre)
    return affectation


def terminer_affectation(affectation):
    affectation.date_fin = timezone.localdate()
    affectation.save(update_fields=["date_fin"])
    synchroniser_classes(affectation.professeur)


# ─────────────────────────────── Secondaire ───────────────────────────────
def quand(jour, creneau):
    return f"le {dict(choices.JOURS_CHOICES)[jour].lower()} en {creneau.nom}"


def conflit_classe(classe, jour, creneau, sauf_professeur=None):
    """Le cours qui occupe déjà cette classe à ce moment, s'il existe."""
    cours = Cours.objects.filter(
        classe=classe, jour=jour, creneau=creneau, annee_scolaire=choices.annee_scolaire_courante(),
    ).select_related("professeur")
    if sauf_professeur is not None and sauf_professeur.pk:
        cours = cours.exclude(professeur=sauf_professeur)
    return cours.first()


def conflit_professeur(professeur, jour, creneau):
    if professeur is None or not professeur.pk:
        return None
    return Cours.objects.filter(
        professeur=professeur, jour=jour, creneau=creneau, annee_scolaire=choices.annee_scolaire_courante(),
    ).select_related("classe").first()


def ajouter_cours(professeur, lignes):
    for ligne in lignes:
        Cours.objects.create(
            professeur=professeur, classe=ligne["classe"], matiere=ligne["matiere"],
            jour=ligne["jour"], creneau=ligne["creneau"],
        )
    synchroniser_classes(professeur)


def cours_de_l_annee(professeur):
    return professeur.cours.filter(annee_scolaire=choices.annee_scolaire_courante()) \
        .select_related("classe", "creneau", "classe__section")


# ─────────────────────────────── Commun ───────────────────────────────
def synchroniser_classes(professeur):
    """Professeur.classes = classe de son affectation + classes de ses cours de l'année."""
    ids = set(professeur.affectations.filter(date_fin__isnull=True).values_list("classe_id", flat=True))
    ids |= set(cours_de_l_annee(professeur).values_list("classe_id", flat=True))
    professeur.classes.set(ids)


def grille(cours, creneaux):
    """Emploi du temps : une ligne par créneau, une case par jour (le cours ou None)."""
    par_case = {(c.jour, c.creneau_id): c for c in cours}
    return [
        {"creneau": creneau, "cases": [par_case.get((jour, creneau.pk)) for jour, _ in choices.JOURS_CHOICES]}
        for creneau in creneaux
    ]


def resume(cours):
    cours = list(cours)
    minutes = sum(c.creneau.duree_minutes for c in cours)
    classes = sorted({c.classe.nom for c in cours})
    return {
        "nb_cours": len(cours),
        "classes": classes,
        "heures": f"{minutes // 60} h {minutes % 60:02d}",
    }
