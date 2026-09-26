# core/notes.py
# Présentation des notes par classe, puis par matière : une ligne par élève et
# une colonne par trimestre. Sert à « Mes notes » (professeur), à la page Notes
# (secrétariat, directions) et à la fiche d'un élève.
from . import choices
from .classes import ordre as _ordre_classe


def _moyenne(valeurs):
    valeurs = [v for v in valeurs if v is not None]
    return sum(valeurs) / len(valeurs) if valeurs else None


def grouper(notes, toute_la_classe=False):
    """[{classe, matieres: [{matiere, professeurs, lignes: [{eleve, cellules, moyenne}], moyennes}]}]

    `cellules` et `moyennes` suivent l'ordre de choices.PERIODES (une case par trimestre).
    Si un élève a deux notes pour la même case, la plus récente compte. Avec
    `toute_la_classe`, chaque tableau montre aussi les élèves sans note.
    """
    periodes = choices.PERIODES
    classes = {}
    for note in sorted(notes, key=lambda n: n.date_note):
        classe = note.eleve.classe
        groupe = classes.setdefault(classe.pk if classe else None, {"classe": classe, "matieres": {}})
        matiere = groupe["matieres"].setdefault(note.matiere, {"matiere": note.matiere, "professeurs": [], "lignes": {}})
        if note.professeur and str(note.professeur) not in matiere["professeurs"]:
            matiere["professeurs"].append(str(note.professeur))
        ligne = matiere["lignes"].setdefault(note.eleve_id, {"eleve": note.eleve, "cellules": [None] * len(periodes)})
        if note.periode in periodes:
            ligne["cellules"][periodes.index(note.periode)] = note

    resultat = []
    for groupe in sorted(classes.values(), key=lambda g: (g["classe"] is None, _ordre_classe(g["classe"]))):
        eleves = list(groupe["classe"].eleves.all()) if toute_la_classe and groupe["classe"] else []
        matieres = []
        for matiere in sorted(groupe["matieres"].values(), key=lambda m: m["matiere"]):
            for eleve in eleves:
                matiere["lignes"].setdefault(eleve.pk, {"eleve": eleve, "cellules": [None] * len(periodes)})
            lignes = sorted(matiere["lignes"].values(), key=lambda l: (l["eleve"].nom, l["eleve"].prenom))
            for ligne in lignes:
                ligne["moyenne"] = _moyenne([n.note if n else None for n in ligne["cellules"]])
            matiere["lignes"] = lignes
            matiere["moyennes"] = [_moyenne([l["cellules"][i].note if l["cellules"][i] else None for l in lignes])
                                   for i in range(len(periodes))]
            matieres.append(matiere)
        groupe["matieres"] = matieres
        groupe["nb_notes"] = sum(1 for m in matieres for l in m["lignes"] for n in l["cellules"] if n)
        resultat.append(groupe)
    return resultat

