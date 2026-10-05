# site_public/contenu.py
# Textes et coordonnées du site public, à compléter par l'école.
# Une valeur vide (None ou liste vide) n'est simplement pas affichée.
from core import choices

NOM = choices.NOM_ECOLE
VILLE = choices.VILLE_ECOLE

# ── Coordonnées (page Contact et bas de chaque page) ──────────────
ADRESSE = None          # ex : "Rue Geffrard, Les Cayes"
TELEPHONES = []         # ex : ["+509 3712 3456", "+509 4412 3456"]
WHATSAPP = None         # ex : "+509 3712 3456" (ouvre une conversation WhatsApp)
COURRIEL = None         # ex : "secretariat@lesnenuphars.edu.ht"
HORAIRES = []           # ex : [("Lundi au vendredi", "7 h 30 à 14 h"), ("Samedi", "8 h à 12 h")]

# ── Admissions ─────────────────────────────────────────────────────
FRAIS = []              # ex : [("Frais d'inscription", "2 500 HTG"), ("Mensualité, primaire", "3 000 HTG")]
DATES = []              # ex : [("Rentrée des classes", "Lundi 5 octobre 2026"), ("Réunion des parents", "...")]
PIECES_A_FOURNIR = [
    "Acte de naissance de l'enfant (original et copie)",
    "Dernier bulletin de l'école précédente (sauf pour la 1re année Kinder)",
    "Deux photos d'identité récentes",
]

# ── Présentation ───────────────────────────────────────────────────
# Grand titre de l'accueil : la deuxième partie est mise en couleur
ACCROCHE = ("École du Kindergarten à la NSIV,", "aux Cayes.")
PRESENTATION = (
    "L'Institution Les Nénuphars accueille les élèves de la 1re année Kinder jusqu'à la NSIV, en trois "
    "sections : Kindergarten, primaire et secondaire. Chaque section a sa direction. Les parents suivent "
    "en ligne les notes, les absences et les bulletins de leurs enfants."
)
HISTOIRE = []                   # un paragraphe par élément de la liste
MOT_DE_LA_DIRECTRICE = []       # idem ; signé par la directrice en chef
VALEURS = []                    # ex : [("Rigueur", "Un travail suivi chaque jour..."), ("Bienveillance", "...")]

# ── Pages « Confidentialité » et « Conditions d'utilisation » ───────
# Date affichée en haut des deux pages : à changer quand leur texte change
MISE_A_JOUR_PAGES_LEGALES = "5 octobre 2026"
# Durée de conservation d'une préinscription qui n'aboutit pas à une inscription.
# À confirmer par la direction ; le secrétariat efface ensuite le dossier (rubrique Préinscriptions).
CONSERVATION_PREINSCRIPTION = "jusqu'à la fin de l'année scolaire demandée"
# Durée de conservation du dossier d'un élève après son départ de l'école (à confirmer par la direction)
CONSERVATION_DOSSIER_ELEVE = "tant que la loi ou l'école en a besoin pour délivrer des certificats et relevés de notes"

# Texte de chaque section, sur l'accueil et la page Niveaux
SECTIONS = {
    choices.SECTION_KINDERGARTEN: {
        "niveaux": "1re à 3e année Kinder",
        "texte": "Éveil, langage, jeux et premières lettres, avec deux maîtresses par classe et une directrice "
                 "dédiée aux tout-petits.",
    },
    choices.SECTION_PRIMAIRE: {
        "niveaux": "1re à 6e année fondamentale",
        "texte": "Un titulaire par classe qui enseigne toutes les matières : lecture, écriture et calcul en français "
                 "et en créole, sciences et éducation civique.",
    },
    choices.SECTION_SECONDAIRE: {
        "niveaux": "7e année fondamentale à NSIV",
        "texte": "Un professeur par matière, sous la conduite d'un directeur pédagogique, du 3e cycle fondamental "
                 "au Nouveau Secondaire et jusqu'aux examens officiels.",
    },
}
