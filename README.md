# Système de Gestion Scolaire — Institution Les Nénuphars

Application Django pour la gestion de l'école : élèves, classes, professeurs,
employés, paiements et notes. Toutes les classes sont prévues, de la
**1ère Année Kindergarten à la NSIV**.

## Installation rapide

```bash
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # Windows : copy .env.example .env
python manage.py migrate        # crée les tables, les 3 sections et les rôles
python manage.py seed_data      # crée les classes, le compte admin et quelques données d'exemple
python manage.py runserver
```

Ouvrez http://127.0.0.1:8000/connexion/ → **admin / admin123** (pour les essais seulement).
Pour essayer l'espace d'un professeur et la saisie des notes : **prof / prof123**.

**Attention :** `seed_data` ne fonctionne qu'avec `DJANGO_DEBUG=1`. En production, créez le
compte de la directrice en chef avec `python manage.py createsuperuser`.

## Réglages (fichier `.env`)

Le code ne contient plus aucun secret. Tous les réglages sont dans le fichier
`.env`, qui n'est jamais envoyé sur GitHub. La liste complète est dans `.env.example`.

- **Développement** : `DJANGO_DEBUG=1` et `DB_ENGINE=sqlite` (rien à installer).
- **Production** : `DJANGO_DEBUG=0`, une `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`,
  puis `DB_ENGINE=postgresql` avec `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` et `DB_PORT`.

## Sections et rôles

- 3 sections : **Kindergarten** (1ère à 3ème Année Kinder), **Primaire** (1ère à 6ème AF),
  **Secondaire** (7ème AF à NSIV, avec un seul directeur pédagogique).
- Les rôles sont des groupes Django : Parent, Professeur, Surveillant, Censeur,
  Secrétariat, Caisse, Direction de section, Directrice en chef. Les droits de chaque
  rôle sont dans `core/roles.py` et suivent le tableau « Droits d'accès » du cahier des charges.
- Le rôle d'un employé suit son poste : quand un compte est relié à une fiche employé
  (champ « utilisateur »), il reçoit le rôle qui correspond au poste. Les directions de
  section, les surveillants et les censeurs ne voient que la section indiquée sur leur fiche.
- Une seule page de connexion pour tout le monde, avec le téléphone, l'e-mail ou le nom
  d'utilisateur. Un compte marqué « doit changer son mot de passe » doit le changer avant
  de faire quoi que ce soit d'autre.

## Professeurs

- C'est la secrétaire qui inscrit le professeur (`/professeurs/nouveau/`). Elle choisit
  d'abord la section, puis le formulaire s'adapte :
  - **Kindergarten** : une classe, deux maîtresses au plus (dont une seule titulaire).
  - **Primaire** : une classe et un seul professeur par classe ; pour le remplacer, la
    secrétaire doit confirmer.
  - **Secondaire** : une ligne par cours (matière, classe, jour, heure). Le site refuse une
    heure déjà prise dans une classe, ou deux cours du professeur à la même heure.
- Le site crée le compte du professeur : l'identifiant est son téléphone, et un mot de
  passe provisoire est donné sur une fiche d'accès à imprimer.
- La direction de la section valide les cours ; le professeur voit ensuite son emploi du
  temps en se connectant.
- Les horaires du secondaire (5 heures de 55 minutes et une récréation) se modifient dans
  `/admin/` (Créneaux).

## Notes

- Ce sont les professeurs qui saisissent les notes (menu « Saisie des notes ») : une grille
  avec les élèves d'une classe, pour une matière et un trimestre. Au secondaire, seulement les
  classes et matières de leurs cours validés ; au Kindergarten et au primaire, toutes les
  matières de leur classe.
- La direction d'une section peut corriger ou retirer une note de sa section.
- La directrice en chef et le compte admin lisent toutes les notes mais ne peuvent pas en
  saisir, ni dans le site ni dans `/admin/`.

## Anniversaires et ancienneté

- Les fiches des professeurs et des employés ont la date de naissance, l'adresse et la date
  d'embauche.
- Le tableau de bord annonce les anniversaires des 7 prochains jours, et les années passées à
  l'école, pour le personnel que chacun a le droit de voir (une direction de section : sa section).
- À la connexion, une petite fenêtre souhaite la bienvenue et rappelle les anniversaires du jour.
  Le professeur dont c'est l'anniversaire reçoit ses vœux sur son espace.

## Icônes

Les icônes viennent de [Bootstrap Icons](https://icons.getbootstrap.com) (licence MIT) et sont
dans un seul fichier, `static/icones/icones.svg`. Dans une page : `{% load icones %}` puis
`{% icone "eleves" %}`. Pour en ajouter une, copiez son `<symbol>` dans ce fichier.

## Structure du projet

```
gestion_ecole/            → réglages Django (settings.py, urls.py)
core/
    models.py             → Utilisateur, Section, Classe, Eleve, Professeur, Employe, Paiement, Note,
                            Creneau, Affectation, Cours
    choices.py            → nom de l'école, classes (Kinder → NSIV), sections, matières, postes, types de paiement
    roles.py              → les rôles et les droits de chacun
    professeurs.py        → règles d'inscription des professeurs (Kindergarten, primaire, secondaire)
    views_professeurs.py  → inscription, fiche et emploi du temps des professeurs
    views_notes.py        → saisie des notes par les professeurs
    anniversaires.py      → anniversaires et années à l'école du personnel
    templatetags/icones.py → balise {% icone "nom" %}
    backends.py           → connexion avec le téléphone, l'e-mail ou le nom d'utilisateur
    forms.py              → formulaires et validation
    views.py              → connexion, espace de chacun, tableau de bord, gestion de chaque module
    tests.py              → tests automatiques (python manage.py test)
    admin.py              → gestion des données dans /admin/
    management/commands/seed_data.py → crée les classes et des données d'exemple
templates/core/           → toutes les pages HTML
static/css/style.css
static/icones/icones.svg  → toutes les icônes du site
```

## Adapter à votre école

- **Nom de l'école et ville** : changez `NOM_ECOLE` et `VILLE_ECOLE` dans `core/choices.py`,
  ainsi que dans `templates/core/login.html` et `base.html` (textes « LES NÉNUPHARS » et « Les Cayes »).
- **Liste des classes** : `CLASSES_PAR_DEFAUT` dans `core/choices.py`. Vous pouvez aussi gérer
  les classes directement dans la rubrique « Classes » de l'application (ajouter, supprimer)
  sans toucher au code.
- **Matières, postes des employés, types de paiement** : tous dans `core/choices.py`.

## Fonctionnalités

- **Élèves** : informations de l'élève, nom et téléphone du parent ou tuteur, classe
  (une seule classe par élève).
- **Classes** : créer et modifier les classes (nom, section, cycle : Préscolaire, Fondamentale
  ou Secondaire, année scolaire).
- **Professeurs** : inscription par la secrétaire selon la section, compte de connexion,
  classe ou emploi du temps validé par la direction.
- **Employés** : le personnel non enseignant (directions, secrétariat, caisse, surveillants,
  censeurs, etc.), avec date de naissance, adresse et date d'embauche.
- **Paiements** : suivi des paiements des élèves (scolarité, inscription, etc.) et total reçu.
- **Notes** : saisies par les professeurs, par matière, trimestre et année scolaire ; lecture et
  recherche pour l'administration.

## Prochaines étapes possibles

- Ajouter un bulletin (relevé de notes) par élève et par trimestre.
- Exporter les listes d'élèves et de paiements en PDF ou en Excel.
- Mettre le site en ligne (Render, Railway, PythonAnywhere).
