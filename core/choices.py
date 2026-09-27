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
# SECTIONS DE L'ÉCOLE (organisation interne, chacune avec sa direction)
# Elles ne suivent pas les cycles officiels : 7ème-9ème AF sont en
# « Fondamentale » mais dépendent du directeur pédagogique du secondaire.
# ========================================
SECTION_KINDERGARTEN = "Kindergarten"
SECTION_PRIMAIRE = "Primaire"
SECTION_SECONDAIRE = "Secondaire"

SECTIONS_PAR_DEFAUT = [SECTION_KINDERGARTEN, SECTION_PRIMAIRE, SECTION_SECONDAIRE]

SECTION_PAR_CLASSE = {
    "1ère Année Kinder": SECTION_KINDERGARTEN,
    "2ème Année Kinder": SECTION_KINDERGARTEN,
    "3ème Année Kinder": SECTION_KINDERGARTEN,
    "1ère AF": SECTION_PRIMAIRE,
    "2ème AF": SECTION_PRIMAIRE,
    "3ème AF": SECTION_PRIMAIRE,
    "4ème AF": SECTION_PRIMAIRE,
    "5ème AF": SECTION_PRIMAIRE,
    "6ème AF": SECTION_PRIMAIRE,
    "7ème AF": SECTION_SECONDAIRE,
    "8ème AF": SECTION_SECONDAIRE,
    "9ème AF": SECTION_SECONDAIRE,
    "NSI": SECTION_SECONDAIRE,
    "NSII": SECTION_SECONDAIRE,
    "NSIII": SECTION_SECONDAIRE,
    "NSIV": SECTION_SECONDAIRE,
}

# ========================================
# PROFESSEURS : rôle dans une classe (Kindergarten et primaire),
# jours de cours et horaires par défaut du secondaire
# ========================================
ROLE_TITULAIRE = "Titulaire"
ROLE_DEUXIEME_MAITRESSE = "Deuxième maîtresse"
ROLES_AFFECTATION_CHOICES = _vers_choix([ROLE_TITULAIRE, ROLE_DEUXIEME_MAITRESSE])

JOURS_CHOICES = [(1, "Lundi"), (2, "Mardi"), (3, "Mercredi"), (4, "Jeudi"), (5, "Vendredi")]

STATUT_COURS_PROPOSE = "Proposé"
STATUT_COURS_VALIDE = "Validé"
STATUTS_COURS_CHOICES = _vers_choix([STATUT_COURS_PROPOSE, STATUT_COURS_VALIDE])

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
POSTE_DIRECTION_GENERALE = "Directeur(trice) en chef"
POSTES_DIRECTION_SECTION = [
    "Directeur(trice) du Kindergarten",
    "Directeur(trice) du primaire",
    "Directeur(trice) pédagogique du secondaire",
]

POSTES_EMPLOYES = [
    POSTE_DIRECTION_GENERALE, *POSTES_DIRECTION_SECTION,
    "Directeur(trice) Adjoint(e)", "Secrétaire",
    "Comptable", "Caissier(ère)", "Surveillant(e)", "Censeur", "Bibliothécaire",
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


def annee_scolaire_courante(aujourd_hui=None):
    """L'année scolaire commence en septembre : le 25/09/2026 donne '2026-2027'."""
    from datetime import date
    jour = aujourd_hui or date.today()
    debut = jour.year if jour.month >= 9 else jour.year - 1
    return f"{debut}-{debut + 1}"


def dates_du_trimestre(periode, annee_scolaire):
    """(premier jour, dernier jour) d'un trimestre, pour compter absences et retards du bulletin.

    1er trimestre : septembre à décembre ; 2e : janvier à mars ; 3e : avril à août.
    """
    from datetime import date
    debut = int(annee_scolaire[:4])
    return {
        PERIODES[0]: (date(debut, 9, 1), date(debut, 12, 31)),
        PERIODES[1]: (date(debut + 1, 1, 1), date(debut + 1, 3, 31)),
        PERIODES[2]: (date(debut + 1, 4, 1), date(debut + 1, 8, 31)),
    }[periode]


def trimestre_du_jour(jour=None):
    from datetime import date
    jour = jour or date.today()
    if jour.month >= 9:
        return PERIODES[0]
    return PERIODES[1] if jour.month <= 3 else PERIODES[2]


def obtenir_annees_scolaires():
    """Génère une liste des 10 dernières années scolaires (ex: '2025-2026')."""
    from datetime import datetime
    annee_courante = datetime.now().year
    return [f"{annee_courante - i}-{annee_courante - i + 1}" for i in range(10, -1, -1)]


# ========================================
# PRÉINSCRIPTIONS : de la demande envoyée par la famille à l'inscription
# ========================================
ETAPE_RECUE = "Reçue"
ETAPE_CHEZ_LA_DIRECTION = "Chez la direction"
ETAPE_ACCEPTEE = "Acceptée"
ETAPE_REFUSEE = "Refusée"
ETAPE_INSCRITE = "Inscrite"
ETAPES_PREINSCRIPTION = [ETAPE_RECUE, ETAPE_CHEZ_LA_DIRECTION, ETAPE_ACCEPTEE, ETAPE_REFUSEE, ETAPE_INSCRITE]
ETAPES_PREINSCRIPTION_CHOICES = _vers_choix(ETAPES_PREINSCRIPTION)
# Demandes pas encore terminées (ni refusées, ni inscrites)
ETAPES_EN_COURS = [ETAPE_RECUE, ETAPE_CHEZ_LA_DIRECTION, ETAPE_ACCEPTEE]


# ========================================
# VIE SCOLAIRE : appel du matin, incidents, conduite
# ========================================
PRESENT = "Présent"
RETARD = "Retard"
ABSENCE = "Absence"
TYPES_ABSENCE_CHOICES = [(ABSENCE, "Absence"), (RETARD, "Retard")]

# Un incident signalé par un surveillant ou un professeur est traité par le censeur
INCIDENT_SIGNALE = "Signalé"
INCIDENT_EN_COURS = "En cours"
INCIDENT_CLOS = "Clos"
STATUTS_INCIDENT = [INCIDENT_SIGNALE, INCIDENT_EN_COURS, INCIDENT_CLOS]
STATUTS_INCIDENT_CHOICES = _vers_choix(STATUTS_INCIDENT)

# Élève tombé malade à l'école : ce que fait l'école (les parents sont prévenus tout de suite)
MESURES_SANTE = ["Se repose à l'école", "Un parent doit venir à l'école", "Conduit(e) chez le médecin"]
MESURES_SANTE_CHOICES = _vers_choix(MESURES_SANTE)

# Activités de l'école montrées sur le site public, avec leurs photos
CATEGORIES_ACTIVITE = ["Génies en herbe", "Concours", "Sortie", "Fête", "Sport", "Autre"]
CATEGORIES_ACTIVITE_CHOICES = _vers_choix(CATEGORIES_ACTIVITE)

# Notifications des parents
NOTIF_ABSENCE = "Absence"
NOTIF_RETARD = "Retard"
NOTIF_COMPORTEMENT = "Comportement"
NOTIF_CONVOCATION = "Convocation"
NOTIF_SANTE = "Santé"
NOTIF_BULLETIN = "Bulletin"
NOTIF_ANNONCE = "Annonce"
CATEGORIES_NOTIFICATION = [NOTIF_ABSENCE, NOTIF_RETARD, NOTIF_COMPORTEMENT, NOTIF_CONVOCATION, NOTIF_SANTE,
                           NOTIF_BULLETIN, NOTIF_ANNONCE]
CATEGORIES_NOTIFICATION_CHOICES = _vers_choix(CATEGORIES_NOTIFICATION)

# Appréciation de conduite du bulletin, donnée par le censeur (ou la direction de la section)
CONDUITES = ["Excellente", "Très bonne", "Bonne", "Passable", "À améliorer"]
CONDUITES_CHOICES = _vers_choix(CONDUITES)
