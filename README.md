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
- **prof / prof123** : un professeur du secondaire, pour la saisie des notes ;
- **surveillant / surveillant123** : le surveillant du secondaire, pour l'appel du matin ;
- **censeur / censeur123** : le censeur du secondaire, pour les absences, les incidents et la conduite ;
- **parent / parent123** : le parent de Marie Martin, pour l'espace parent.

`seed_data` affiche aussi un code d'accès pour la famille de Jean Dupont (téléphone
509-3456-7890), à essayer sur http://127.0.0.1:8000/inscription/.

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

## Comptes parents

- Il n'y a pas d'inscription libre : sans code, personne ne voit les données d'un élève.
- Quand le secrétariat clique sur « Inscrire l'élève », la famille est retrouvée par son
  téléphone (ou créée) et reçoit un **code d'accès** à usage unique, par exemple `NEN-4K7P-29`.
  Frères et sœurs avec le même téléphone : une seule famille, un seul code. Pour un élève déjà
  inscrit, le bouton « Créer l'accès parent » est sur sa fiche.
- La « fiche d'accès » (menu « Comptes parents », ou fiche de l'élève) s'imprime et se remet à la
  famille : l'adresse de la page, le code et le téléphone. Code perdu : « Nouveau code »
  (l'ancien ne sert plus).
- Le parent va sur `/inscription/` (lien « Nouveau parent ? » sur la page de connexion et en bas
  du site), entre le code et son téléphone, voit les noms de ses enfants et choisit son mot de
  passe. Il se connecte ensuite avec son téléphone. Si ce téléphone a déjà un compte (un
  professeur qui est aussi parent), ses enfants sont ajoutés à ce compte avec son mot de passe.
- Après 10 essais ratés en 15 minutes, la page se bloque pour cette adresse.
- L'espace parent (`/parents/`) montre, pour chaque enfant, les annonces, les notes de l'année
  par matière et par trimestre, les bulletins validés, les absences et retards, le comportement
  et les paiements. Un parent ne voit que ses enfants.
- Mot de passe oublié : le secrétariat donne un mot de passe provisoire depuis la fiche d'accès
  (seulement pour un compte qui ne sert qu'aux parents).

## Vie scolaire : appel, absences, incidents

- **Appel du matin** (menu « Appel du matin », fait pour le téléphone) : le surveillant choisit
  une classe de sa section ; tout le monde est présent au départ, il touche R (retard, avec les
  minutes) ou A (absent). Un professeur peut aussi faire l'appel de ses classes. On peut refaire
  l'appel de la journée pour le corriger.
- **Tableau de la vie scolaire** (menu « Vie scolaire ») : absents et retards du jour (ou d'un
  autre jour), incidents ouverts, convocations à venir. Le censeur ou la direction de la section
  justifie une absence avec son motif.
- **Incidents** : un surveillant ou un professeur signale un incident. Le censeur ou la direction
  de la section décide de la suite (sanction, statut, convocation des parents) et coche
  **« Informer les parents »** s'il veut que la famille le sache. Une convocation informe toujours
  les parents ; elle s'imprime depuis la fiche de l'incident.
- **Élève malade** (bouton sur l'appel du matin et la vie scolaire) : le surveillant, le professeur
  ou le censeur indique ce que l'élève a et ce que fait l'école (il se repose, un parent doit
  venir, il est conduit chez le médecin). Les parents reçoivent une notification tout de suite, et
  la page propose d'appeler la famille ou de la prévenir par WhatsApp.
- **Ce que voient les parents** : les absences et retards tout de suite ; un incident seulement
  si le censeur a coché « Informer les parents », avec la suite donnée et la date de convocation ;
  les alertes santé.

## Bulletins trimestriels

- Menu « Bulletins » : pour chaque classe et chaque trimestre, l'avancement de la saisie des notes.
- Calcul (en attendant les règles de l'école, dans `core/bulletins.py`) : toutes les matières
  comptent pareil, la moyenne générale est la moyenne des matières notées, deux élèves à égalité
  ont le même rang, les absences et retards comptent du début à la fin du trimestre
  (1er : septembre à décembre, 2e : janvier à mars, 3e : avril à août).
- Le censeur donne la **conduite** de chaque élève ; la direction de la section écrit son
  **appréciation** puis **valide** les bulletins de la classe. Les valeurs sont alors figées :
  une note corrigée plus tard ne change pas un bulletin publié. « Retirer la publication »
  permet de corriger puis de valider de nouveau.
- Les parents voient un bulletin seulement quand il est validé. Ils peuvent l'imprimer ou le
  **télécharger en PDF ou en image (PNG)**, pratique à envoyer par WhatsApp.
- L'école imprime tous les bulletins d'une classe en un clic, télécharge la classe dans un seul PDF
  (une page par élève), ou le bulletin d'un élève en PDF ou en PNG. Les fichiers sont faits par le
  serveur (`core/bulletins_fichiers.py`, avec ReportLab et pypdfium2).

## Annonces aux parents

- Menu « Annonces » : le secrétariat et la directrice en chef écrivent à toute l'école, à une
  section ou à une classe ; la direction d'une section, à sa section ou à l'une de ses classes.
- Le parent voit les annonces qui concernent ses enfants dans son espace et dans son menu
  « Annonces ».

## Notifications des parents

- Le parent reçoit une notification pour : une absence ou un retard à l'appel, un incident dont
  le censeur veut l'informer, une convocation, un élève malade, un bulletin publié, une annonce.
- Le menu « Notifications » affiche le nombre de nouvelles ; la fenêtre de bienvenue les résume à
  la connexion, et l'espace parent les montre en haut (« Nouveau pour vous »).
- Une notification suit ce qui l'a créée : si l'appel est corrigé ou un bulletin retiré, elle
  disparaît ; si une absence est justifiée, elle est mise à jour.
- Les notifications restent sur le site. Pour un message urgent, les pages de l'incident et de
  l'élève malade ont un bouton « Prévenir aussi par WhatsApp » (le message est déjà écrit) et
  « Appeler la famille ».

## Navigation

- Chaque page a une **flèche de retour** en haut à gauche : elle ramène à la page d'avant dans
  l'application (sans revenir sur un formulaire déjà enregistré), ou à l'accueil de chacun.

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
                            Creneau, Affectation, Cours, Preinscription, MessageContact, Parent,
                            Annonce, Appel, Absence, Incident, AlerteSante, Bulletin, Notification
    choices.py            → nom de l'école, classes (Kinder → NSIV), sections, matières, postes, types de paiement
    roles.py              → les rôles et les droits de chacun
    professeurs.py        → règles d'inscription des professeurs (Kindergarten, primaire, secondaire)
    views_professeurs.py  → inscription, fiche et emploi du temps des professeurs
    views_notes.py        → saisie des notes par les professeurs, « Mes notes »
    views_fiches.py       → fiches d'un élève, d'une classe, d'un employé, et photos protégées
    views_admissions.py   → suivi des préinscriptions et messages du site
    parents.py            → codes d'accès et création des comptes parents
    views_parents.py      → « Créer mon compte parent », espace parent, comptes parents du secrétariat
    views_vie_scolaire.py → appel du matin, tableau du censeur, incidents et convocations
    bulletins.py          → calcul, validation et publication des bulletins trimestriels
    bulletins_fichiers.py → bulletins à télécharger en PDF et en image (PNG)
    views_bulletins.py    → pages des bulletins (par classe, par élève, impression, téléchargement)
    notifications.py      → notifications des parents et lien « Prévenir par WhatsApp »
    views_annonces.py     → annonces aux parents
    notes.py              → notes par classe, puis par matière
    photos.py             → réduction et rangement des photos
    anniversaires.py      → anniversaires et années à l'école du personnel
    templatetags/icones.py → balise {% icone "nom" %}
    backends.py           → connexion avec le téléphone, l'e-mail ou le nom d'utilisateur
    forms.py              → formulaires et validation
    views.py              → connexion, espace de chacun, tableau de bord, gestion de chaque module
    tests*.py             → tests automatiques (python manage.py test)
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
- **Comptes parents** : code d'accès remis à l'inscription, espace parent avec les annonces, les
  notes, les bulletins, les absences, le comportement, la santé et les paiements de ses enfants,
  et des notifications.
- **Vie scolaire** : appel du matin sur téléphone, absences et retards, incidents, sanctions,
  convocations des parents, élève malade.
- **Bulletins** : bulletin trimestriel par élève (moyenne, rang, absences, conduite, appréciation),
  validé par la direction puis publié aux parents, à imprimer ou télécharger en PDF et en image.
- **Annonces** : messages aux parents de toute l'école, d'une section ou d'une classe.
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

- Coefficients par matière et règles de passage de l'école dans le calcul des bulletins.
- Envoyer les notifications aussi par SMS ou WhatsApp automatiquement (il faut un fournisseur
  d'envoi, payant).
- Ajouter les actualités, le calendrier et la galerie au site public.
- Montrer aux parents le solde à payer (il faut d'abord enregistrer les frais de chaque classe).
- Exporter les listes d'élèves et de paiements en PDF ou en Excel.
- Mettre le site en ligne (Render, Railway, PythonAnywhere).
