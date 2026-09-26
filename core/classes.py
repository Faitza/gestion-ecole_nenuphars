# core/classes.py
# Ordre naturel des classes : Kindergarten, puis primaire, puis secondaire, et
# dans chaque section l'ordre de choices.CLASSES_PAR_DEFAUT.
from . import choices


def ordre(classe):
    if classe is None:
        return (99, 99, "")
    noms = [nom for nom, _ in choices.CLASSES_PAR_DEFAUT]
    section = classe.section.ordre if classe.section_id else 99
    return (section, noms.index(classe.nom) if classe.nom in noms else 99, classe.nom)


def dans_l_ordre(classes):
    return sorted(classes, key=ordre)


def par_section(classes):
    """[(section ou None, [classes])] dans l'ordre des sections."""
    groupes = {}
    for classe in dans_l_ordre(classes):
        groupes.setdefault(classe.section, []).append(classe)
    return list(groupes.items())
