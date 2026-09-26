# core/telephone.py
import re


def normaliser_telephone(valeur):
    """Garde les chiffres et ajoute l'indicatif 509 à un numéro haïtien à 8 chiffres.

    « 3712 3456 », « +509 3712-3456 » et « 50937123456 » donnent tous « 50937123456 ».
    """
    chiffres = re.sub(r"\D", "", valeur or "")
    if len(chiffres) == 8:
        chiffres = "509" + chiffres
    return chiffres
