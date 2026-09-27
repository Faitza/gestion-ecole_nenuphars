# core/bulletins.py
# Bulletin trimestriel (cahier des charges, sections D et H) : note de chaque
# matière, moyenne générale, rang dans la classe, absences et retards du
# trimestre, conduite (censeur) et appréciation (direction). La direction de
# la section valide les bulletins d'une classe ; les valeurs sont alors
# figées et les parents les voient.
#
# Règles de calcul (en attendant celles de l'école) : toutes les matières
# comptent pareil, la moyenne générale est la moyenne des matières notées, et
# deux élèves à égalité ont le même rang.
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from . import choices
from .models import Absence, Bulletin, Cours, Note

ETAT_VALIDES = "Validés"
ETAT_A_VALIDER = "À valider"
ETAT_INCOMPLET = "Notes manquantes"
ETAT_VIDE = "Pas encore de notes"


def _arrondi(valeur):
    return None if valeur is None else Decimal(valeur).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _moyenne(valeurs):
    valeurs = [v for v in valeurs if v is not None]
    return _arrondi(sum(valeurs) / len(valeurs)) if valeurs else None


def matieres_attendues(classe, annee):
    """Les matières des cours validés de la classe (secondaire), plus celles déjà notées."""
    return set(Cours.objects.filter(classe=classe, annee_scolaire=annee, statut=choices.STATUT_COURS_VALIDE)
               .values_list("matiere", flat=True))


def calculer(classe, periode, annee):
    """{eleve.pk: {eleve, lignes, moyenne, rang, effectif, absences, retards}} pour toute la classe."""
    eleves = list(classe.eleves.order_by("nom", "prenom"))
    notes = {}
    for note in Note.objects.filter(eleve__classe=classe, periode=periode, annee_scolaire=annee) \
            .select_related("professeur").order_by("date_note"):
        notes[(note.eleve_id, note.matiere)] = note  # la plus récente compte
    matieres = sorted({m for _, m in notes} | matieres_attendues(classe, annee))
    moyennes_classe = {m: _moyenne([n.note for (_, mat), n in notes.items() if mat == m]) for m in matieres}

    debut, fin = choices.dates_du_trimestre(periode, annee)
    compte = dict(
        (ligne["eleve"], ligne) for ligne in Absence.objects.filter(eleve__in=eleves, date__range=(debut, fin))
        .order_by().values("eleve")
        .annotate(absences=Count("pk", filter=Q(type=choices.ABSENCE)), retards=Count("pk", filter=Q(type=choices.RETARD)))
    )

    resultat = {}
    for eleve in eleves:
        lignes = []
        for matiere in matieres:
            note = notes.get((eleve.pk, matiere))
            lignes.append({
                "matiere": matiere,
                "note": str(note.note) if note else None,
                "moyenne_classe": str(moyennes_classe[matiere]) if moyennes_classe[matiere] is not None else None,
                "professeur": str(note.professeur) if note and note.professeur else "",
            })
        resultat[eleve.pk] = {
            "eleve": eleve, "lignes": lignes,
            "moyenne": _moyenne([Decimal(l["note"]) for l in lignes if l["note"] is not None]),
            "absences": compte.get(eleve.pk, {}).get("absences", 0),
            "retards": compte.get(eleve.pk, {}).get("retards", 0),
            "effectif": len(eleves), "rang": None,
        }
    # Rang : 1, 2, 2, 4... parmi les élèves qui ont une moyenne
    classes = sorted((r for r in resultat.values() if r["moyenne"] is not None), key=lambda r: -r["moyenne"])
    for position, r in enumerate(classes, start=1):
        precedent = classes[position - 2] if position > 1 else None
        r["rang"] = precedent["rang"] if precedent and precedent["moyenne"] == r["moyenne"] else position
    return resultat


def avancement(classe, periode, annee):
    """Où en est la classe pour ce trimestre : notes saisies, et bulletins validés ou non."""
    effectif = classe.eleves.count()
    notees = Note.objects.filter(eleve__classe=classe, periode=periode, annee_scolaire=annee)
    matieres = set(notees.values_list("matiere", flat=True)) | matieres_attendues(classe, annee)
    saisies = notees.order_by().values("eleve", "matiere").distinct().count()
    attendues = effectif * len(matieres)
    pourcentage = round(100 * saisies / attendues) if attendues else 0
    valides = Bulletin.objects.filter(classe=classe, periode=periode, annee_scolaire=annee, valide=True).count()
    if effectif and valides >= effectif:
        etat = ETAT_VALIDES
    elif not saisies:
        etat = ETAT_VIDE
    elif saisies < attendues:
        etat = ETAT_INCOMPLET
    else:
        etat = ETAT_A_VALIDER
    return {"effectif": effectif, "matieres": len(matieres), "saisies": saisies, "attendues": attendues,
            "pourcentage": pourcentage, "etat": etat, "valides": valides}


def brouillons(classe, periode, annee):
    """Les bulletins déjà enregistrés de la classe (conduite, appréciation), par élève."""
    return {b.eleve_id: b for b in Bulletin.objects.filter(classe=classe, periode=periode, annee_scolaire=annee)}


def enregistrer_remarques(classe, periode, annee, remarques):
    """remarques = {eleve.pk: {"conduite": ..., "appreciation": ...}} (seulement les champs donnés)."""
    existants = brouillons(classe, periode, annee)
    for eleve_pk, champs in remarques.items():
        bulletin = existants.get(eleve_pk) or Bulletin(eleve_id=eleve_pk, classe=classe, periode=periode,
                                                       annee_scolaire=annee)
        for champ, valeur in champs.items():
            setattr(bulletin, champ, valeur)
        bulletin.save()


@transaction.atomic
def valider(classe, periode, annee, par):
    """Fige le bulletin de chaque élève de la classe et le publie aux parents."""
    existants = brouillons(classe, periode, annee)
    maintenant = timezone.now()
    for eleve_pk, r in calculer(classe, periode, annee).items():
        bulletin = existants.get(eleve_pk) or Bulletin(eleve_id=eleve_pk, periode=periode, annee_scolaire=annee)
        bulletin.classe = classe
        bulletin.lignes = r["lignes"]
        bulletin.moyenne, bulletin.rang, bulletin.effectif = r["moyenne"], r["rang"], r["effectif"]
        bulletin.absences, bulletin.retards = r["absences"], r["retards"]
        bulletin.valide, bulletin.valide_par, bulletin.valide_le = True, par, maintenant
        bulletin.save()


def retirer(classe, periode, annee):
    """Les bulletins ne sont plus visibles par les parents (pour une correction)."""
    Bulletin.objects.filter(classe=classe, periode=periode, annee_scolaire=annee).update(valide=False)


def apercu(bulletin_ou_calcul):
    """Ce que montre la page d'un bulletin, qu'il soit validé (valeurs figées) ou non (calcul du moment)."""
    b = bulletin_ou_calcul
    if isinstance(b, Bulletin):
        return {"lignes": [{**l, "note": _arrondi(l["note"]) if l["note"] else None,
                            "moyenne_classe": _arrondi(l["moyenne_classe"]) if l["moyenne_classe"] else None}
                           for l in b.lignes],
                "moyenne": b.moyenne, "rang": b.rang, "effectif": b.effectif,
                "absences": b.absences, "retards": b.retards}
    return {**b, "lignes": [{**l, "note": _arrondi(l["note"]) if l["note"] else None,
                             "moyenne_classe": _arrondi(l["moyenne_classe"]) if l["moyenne_classe"] else None}
                            for l in b["lignes"]]}
