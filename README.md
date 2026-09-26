# Système de Gestion Scolaire — Institution Les Nénuphars

Site de l'école et application Django pour sa gestion : site public avec préinscription en
ligne, élèves, classes, professeurs, employés, paiements et notes. Toutes les classes sont
prévues, de la **1ère Année Kindergarten à la NSIV**.

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

Ouvrez http://127.0.0.1:8000/ pour le site public, et http://127.0.0.1:8000/connexion/ pour
la gestion (elle est sous `/gestion/`). Comptes d'essai (pour les essais seulement) :

- **admin / admin123** : compte administrateur ;
- **secretaire / secretaire123** : la secrétaire ;
- **direction / direction123** : la direction du primaire, pour accepter les préinscriptions ;
- **prof / prof123** : un professeur du secondaire, pour la saisie des notes.

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
- Les notes s'affichent par classe, puis par matière, avec une colonne par trimestre et les
  moyennes : dans « Mes notes » pour le professeur (il y arrive après l'enregistrement), et dans
  la page Notes pour la secrétaire et les directions, qui les voient dès qu'elles sont enregistrées.
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

## Fiches et photos

- En cliquant sur une classe, on voit ses élèves et ses professeurs. En cliquant sur un élève ou
  un employé, on voit sa fiche avec seulement ses informations (le salaire reste réservé à la
  directrice en chef et à la caisse).
- Élèves, professeurs et employés peuvent avoir une photo d'identité (5 Mo au plus). Sur un
  téléphone, le bouton propose aussi l'appareil photo. La photo est réduite à 800 px et ne
  s'affiche qu'aux personnes qui ont le droit de voir la fiche : elle n'a pas d'adresse publique.
- Les photos sont rangées dans le dossier `media/` (ou `DJANGO_MEDIA_ROOT`), qui n'est pas envoyé
  sur GitHub. Pensez à le sauvegarder avec la base de données.

## Site public et préinscriptions

- Pages ouvertes à tous : Accueil (`/`), L'école, Niveaux, Admissions et Contact. Les textes,
  l'adresse, les téléphones, WhatsApp, les horaires, les frais et les dates sont dans
  `site_public/contenu.py` : ce qui est vide n'est pas affiché.
- Une famille remplit la préinscription sur son téléphone (avec, si elle veut, la photo de
  l'enfant, l'acte de naissance et le dernier bulletin, en PDF ou en photo) et reçoit un
  numéro de dossier, par exemple `PRE-2026-0147`. Le secrétariat peut aussi la saisir pour elle
  (bouton « Saisir une demande »).
- Dans « Préinscriptions », le dossier suit ses étapes : **reçue**, **chez la direction**,
  **acceptée** ou **refusée**, puis **inscrite**. Le secrétariat vérifie le dossier, note le
  rendez-vous et le transmet ; la direction de la section (ou la directrice en chef) accepte ou
  refuse ; le secrétariat clique sur « Inscrire l'élève », ce qui crée sa fiche dans la classe
  demandée, avec sa photo.
- Une direction de section ne voit que les demandes de sa section. Les pièces jointes et les
  photos ne sont visibles que par ceux qui voient le dossier.
- Les messages de la page Contact arrivent dans « Messages du site » (secrétariat).
- Un champ caché aux visiteurs arrête les robots qui remplissent les formulaires.

## Icônes

Les icônes viennent de [Bootstrap Icons](https://icons.getbootstrap.com) (licence MIT) et sont
dans un seul fichier, `static/icones/icones.svg`. Dans une page : `{% load icones %}` puis
`{% icone "eleves" %}`. Pour en ajouter une, copiez son `<symbol>` dans ce fichier.

## Structure du projet

```
gestion_ecole/            → réglages Django (settings.py, urls.py)
site_public/              → site public : pages, préinscription, contact
    contenu.py            → textes et coordonnées de l'école, à compléter
core/
    models.py             → Utilisateur, Section, Classe, Eleve, Professeur, Employe, Paiement, Note,
                            Creneau, Affectation, Cours, Preinscription, MessageContact
    choices.py            → nom de l'école, classes (Kinder → NSIV), sections, matières, postes, types de paiement
    roles.py              → les rôles et les droits de chacun
    professeurs.py        → règles d'inscription des professeurs (Kindergarten, primaire, secondaire)
    views_professeurs.py  → inscription, fiche et emploi du temps des professeurs
    views_notes.py        → saisie des notes par les professeurs, « Mes notes »
    views_fiches.py       → fiches d'un élève, d'une classe, d'un employé, et photos protégées
    views_admissions.py   → suivi des préinscriptions et messages du site
    notes.py              → notes par classe, puis par matière
    photos.py             → réduction et rangement des photos
    anniversaires.py      → anniversaires et années à l'école du personnel
    templatetags/icones.py → balise {% icone "nom" %}
    backends.py           → connexion avec le téléphone, l'e-mail ou le nom d'utilisateur
    forms.py              → formulaires et validation
    views.py              → connexion, espace de chacun, tableau de bord, gestion de chaque module
    tests.py              → tests automatiques (python manage.py test)
    admin.py              → gestion des données dans /admin/
    management/commands/seed_data.py → crée les classes et des données d'exemple
templates/core/           → les pages de la gestion
templates/site_public/    → les pages du site public
static/css/style.css      → gestion ; static/css/site.css → site public
static/icones/icones.svg  → toutes les icônes du site
```

## Adapter à votre école

- **Textes et coordonnées du site public** : `site_public/contenu.py`.
- **Nom de l'école et ville** : changez `NOM_ECOLE` et `VILLE_ECOLE` dans `core/choices.py`,
  ainsi que dans `templates/core/login.html` et `base.html` (textes « LES NÉNUPHARS » et « Les Cayes »).
- **Liste des classes** : `CLASSES_PAR_DEFAUT` dans `core/choices.py`. Vous pouvez aussi gérer
  les classes directement dans la rubrique « Classes » de l'application (ajouter, supprimer)
  sans toucher au code.
- **Matières, postes des employés, types de paiement** : tous dans `core/choices.py`.

## Fonctionnalités

- **Site public** : présentation de l'école, niveaux, admissions, contact et préinscription en
  ligne avec numéro de dossier.
- **Préinscriptions** : suivi de chaque demande jusqu'à l'inscription de l'élève.
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
- Ajouter les actualités, le calendrier et la galerie au site public.
- Remettre un code d'accès aux parents à l'inscription, pour leur espace.
- Exporter les listes d'élèves et de paiements en PDF ou en Excel.
- Mettre le site en ligne (Render, Railway, PythonAnywhere).
