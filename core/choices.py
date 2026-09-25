# core/choices.py
# Listes de choix adaptées à une école fondamentale/secondaire haïtienne.
# NOM_ECOLE et les classes sont facilement modifiables ici selon l'établissement.

NOM_ECOLE = "Institution Les Nénuphars"
VILLE_ECOLE = "Les Cayes"


def _vers_choix(liste):
    """Transforme une liste de chaînes en tuples (valeur, étiquette) pour Django."""
    return [(v, v) for v in liste]


# ========================================
# GENRES
# ========================================
GENRES = ["Masculin", "Féminin"]
GENRES_CHOICES = _vers_choix(GENRES)

# ========================================
# CYCLES / CLASSES
# Système haïtien : Fondamentale (1ère-9ème AF) + NS (Nouveau Secondaire I-IV)
# Modifie cette liste selon les classes réellement offertes par l'école.
# ========================================
CYCLES = ["Préscolaire", "Fondamentale", "Secondaire"]
CYCLES_CHOICES = _vers_choix(CYCLES)

# Gamme complète, de la 1ère année Kindergarten à la NS4
CLASSES_PAR_DEFAUT = [
    ("1ère Année Kinder", "Préscolaire"), ("2ème Année Kinder", "Préscolaire"), ("3ème Année Kinder", "Préscolaire"),
    ("1ère AF", "Fondamentale"), ("2ème AF", "Fondamentale"), ("3ème AF", "Fondamentale"),
    ("4ème AF", "Fondamentale"), ("5ème AF", "Fondamentale"), ("6ème AF", "Fondamentale"),
    ("7ème AF", "Fondamentale"), ("8ème AF", "Fondamentale"), ("9ème AF", "Fondamentale"),
    ("NSI", "Secondaire"), ("NSII", "Secondaire"), ("NSIII", "Secondaire"), ("NSIV", "Secondaire"),
]

# ========================================
# MATIÈRES (utilisées pour les professeurs et les notes)
# ========================================
MATIERES = [
    "ETAP", "Informatique", "Français", "Créole", "Mathématiques",
    "Sciences Expérimentales", "Sciences Sociales", "Histoire", "Géographie",
    "Anglais", "Espagnol", "Éducation Physique et Sportive", "Arts Plastiques",
    "Musique", "Éducation Civique et Morale", "Philosophie", "Autre",
]
MATIERES_CHOICES = _vers_choix(MATIERES)

# ========================================
# POSTES DES EMPLOYÉS (personnel non-enseignant)
# ========================================
POSTES_EMPLOYES = [
    "Directeur(trice)", "Directeur(trice) Adjoint(e)", "Secrétaire",
    "Comptable", "Caissier(ère)", "Surveillant(e)", "Bibliothécaire",
    "Agent d'Entretien", "Gardien", "Infirmier(ère)", "Cuisinier(ère)",
    "Chauffeur", "Technicien Informatique", "Autre",
]
POSTES_CHOICES = _vers_choix(POSTES_EMPLOYES)

# ========================================
# TYPES DE PAIEMENT
# ========================================
TYPES_PAIEMENT = [
    "Frais d'Inscription", "Frais de Scolarité (mensualité)", "Réinscription",
    "Frais d'Examen", "Uniforme", "Livres/Matériel", "Cantine", "Transport",
    "Activités Parascolaires", "Autre",
]
TYPES_PAIEMENT_CHOICES = _vers_choix(TYPES_PAIEMENT)

METHODES_PAIEMENT = ["Espèces", "Carte Bancaire", "Virement Bancaire", "Chèque", "Mobile Money (MonCash/NatCash)", "Autre"]
METHODES_PAIEMENT_CHOICES = _vers_choix(METHODES_PAIEMENT)

STATUTS_PAIEMENT = ["Payé", "En attente", "Partiel", "Annulé", "Remboursé"]
STATUTS_PAIEMENT_CHOICES = _vers_choix(STATUTS_PAIEMENT)

# ========================================
# PÉRIODES D'ÉVALUATION (trimestre, comme dans le système scolaire haïtien)
# ========================================
PERIODES = ["1er Trimestre", "2e Trimestre", "3e Trimestre"]
PERIODES_CHOICES = _vers_choix(PERIODES)


def obtenir_annees_scolaires():
    """Génère une liste des 10 dernières années scolaires (ex: '2025-2026')."""
    from datetime import datetime
    annee_courante = datetime.now().year
    return [f"{annee_courante - i}-{annee_courante - i + 1}" for i in range(10, -1, -1)]
