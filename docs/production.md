# Mettre le site en ligne et le garder en bonne santé

Ce document suit la liste des 20 points à vérifier avant d'ouvrir le site aux familles.
Pour chaque point : ce que fait le site, et ce qu'il reste à faire chez l'hébergeur.

## Les 20 points

| # | Point | Dans le site | Reste à faire |
|---|-------|--------------|---------------|
| 01 | Limiter les requêtes par visiteur | 600 pages par minute par compte connecté, ou par adresse IP pour le site public (les photos sont comptées à part) ; connexion : 10 essais en 5 minutes par compte ; préinscription et contact : 30 envois en 10 minutes par adresse. Au-delà, une page « Patientez un peu » (`core/protection.py`). | Mettre `DJANGO_DERRIERE_UN_PROXY=1` chez l'hébergeur, sinon tous les visiteurs ont la même adresse. |
| 02 | Plafonner les appels d'API | Sans objet : le site n'appelle aucun service extérieur payant (WhatsApp est un simple lien). | Si un jour on envoie des SMS automatiques, plafonner ce service. |
| 03 | Plafonner les dépenses chez les fournisseurs d'API | Sans objet, même raison. | Mettre une alerte de budget chez l'hébergeur. |
| 04 | Un message quand ça plante | Pages d'erreur en français : 404, 403, 500, page expirée, envoi trop lourd, trop de demandes (`templates/`). | — |
| 05 | Un chargement au lieu d'un écran blanc | Barre de chargement en haut de chaque page, et bouton « Enregistrer » qui tourne pendant l'envoi (`static/js/chargement.js`). | — |
| 06 | Prévoir le cas où il n'y a rien à afficher | Chaque liste affiche déjà un message (« Aucun élève trouvé », etc.). | — |
| 07 | Gérer les requêtes qui échouent | Erreurs des formulaires affichées en clair ; après 20 secondes sans réponse, un avertissement « connexion lente » et le bouton redevient utilisable ; avertissement « pas de connexion Internet ». | — |
| 08 | Gérer les API qui ne répondent pas | Pas d'API extérieure. Le seul service extérieur est l'envoi d'e-mails : il abandonne après 10 secondes. | — |
| 09 | Empêcher le double clic sur « Envoyer » | Tous les formulaires : le bouton se bloque au premier clic. | — |
| 10 | Empêcher le double paiement | Un formulaire de paiement envoyé deux fois n'enregistre qu'un paiement ; le même paiement (élève, montant, type) dans les 15 minutes doit être confirmé. | — |
| 11 | Ne charger que les données affichées | Listes découpées en pages ; un test vérifie que la liste des élèves ne fait pas une requête par élève. | — |
| 12 | Des index pour accélérer les recherches | Index sur les élèves (nom), les notes (année, trimestre), les paiements, les absences, les incidents, les préinscriptions, les messages, les annonces, les activités (migration 0013). | La recherche « contient » (nom partiel) n'utilise pas d'index ; à l'échelle d'une école, elle reste rapide. |
| 13 | Découper les longues listes en pages | 50 lignes par page : élèves, professeurs, employés, paiements, préinscriptions, messages, comptes parents, annonces ; 20 activités ; 12 sur le site public. | — |
| 14 | Compresser les fichiers envoyés | Photos réduites et réenregistrées en JPEG (déjà en place). CSS et JavaScript compressés (gzip et brotli) par WhiteNoise. | — |
| 15 | Limiter le poids des fichiers envoyés | 5 Mo par photo ou pièce, 10 Mo par photo d'activité, 20 photos par envoi, 60 Mo par envoi en tout, refusé avant d'être lu. Le navigateur prévient aussi avant d'envoyer. | Régler la même limite chez l'hébergeur s'il en propose une. |
| 16 | Garder en mémoire ce qui ne change pas | CSS, icônes et JavaScript gardés un an par le navigateur (le nom change à chaque modification) ; photos gardées une journée ; sections et classes du site public gardées en mémoire et oubliées dès qu'une classe change. | — |
| 17 | Être alerté si le site tombe | Adresse `/sante/` qui vérifie la base et répond « ok ». | Créer l'alerte (voir plus bas). |
| 18 | Garder une trace de chaque erreur | Journal `logs/erreurs.log` (10 fichiers de 5 Mo), console de l'hébergeur, et e-mail aux adresses de `DJANGO_ADMINS` à chaque erreur. | Remplir `DJANGO_ADMINS` et les réglages `EMAIL_*`. |
| 19 | Tester avec plusieurs visiteurs en même temps | Script `outils/test_charge.py`. Essai fait : 30 visiteurs pendant 30 secondes, environ 200 pages par seconde, médiane 134 ms, aucune erreur. | Le relancer sur le serveur choisi avant l'ouverture. |
| 20 | Vérifier que la sauvegarde se restaure | `sauvegarder` crée un .zip (base + photos) puis le restaure dans une base à part pour le vérifier ; `verifier_sauvegarde` et `restaurer_sauvegarde` (voir plus bas). | Programmer la sauvegarde chaque nuit et en garder une copie hors du serveur. |

## Apparence et crédibilité du site public

| Point | État |
|-------|------|
| Faux avis | Aucun avis ni témoignage sur le site. |
| Mention « fait avec l'IA » | Aucune. |
| Animation du curseur, animations exagérées au défilement | Aucune. Les petits effets au survol s'arrêtent si le téléphone demande moins d'animations. |
| Titre d'accueil vague | Remplacé par ce que l'école est et où : « École du Kindergarten à la NSIV, aux Cayes. » (`site_public/contenu.py`). |
| Dégradés violets | Aucun : couleurs de l'école (bleu marine, rose nénuphar, vert). |
| Tirets longs (—) dans les textes | Aucun sur le site public ; un test le vérifie. |
| Faux chiffres | Les chiffres de l'accueil viennent de la base (classes, sections) ou des réglages de l'école (matières, bulletins par an). |
| Photos générées par IA | Aucune : seules les photos d'activités envoyées par l'école. L'image d'accueil est un dessin de nénuphars. |
| Emojis à la place des icônes | Aucun : vraies icônes (`static/icones/icones.svg`). |
| Textes qui sonnent « IA » | Textes courts et concrets ; à relire par la direction quand elle remplit `contenu.py`. |
| Boutons en forme de pilule | Retirés : filtres, onglets et étiquettes ont des coins légèrement arrondis comme les autres boutons. |
| Page RGPD | Page « Confidentialité » (`/confidentialite/`), liée en bas de chaque page et sous chaque formulaire. Les durées de conservation sont dans `contenu.py`, à confirmer par la direction. |
| Favicon | Icône de l'école (SVG, plus PNG pour les anciens navigateurs et l'écran d'accueil des iPhone). |
| Nom de domaine | À choisir et acheter avec l'hébergeur (par exemple lesnenuphars.edu.ht ou lesnenuphars.ht), puis l'ajouter à `DJANGO_ALLOWED_HOSTS` et `DJANGO_CSRF_TRUSTED_ORIGINS`. |
| Page CGU | Page « Conditions d'utilisation » (`/conditions-d-utilisation/`). |

Les polices sont servies par le site lui-même (`static/fonts/`) : aucune visite n'est
transmise à Google, ce que dit la page Confidentialité.

## Démarrer le site en production

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn gestion_ecole.wsgi --workers 3 --timeout 60
```

Variables à définir chez l'hébergeur (liste complète dans `.env.example`) : `DJANGO_DEBUG=0`,
`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, la base PostgreSQL
(`DB_*`), `DJANGO_MEDIA_ROOT` sur un disque qui ne s'efface pas, `DJANGO_DERRIERE_UN_PROXY=1`,
`DJANGO_ADMINS` et les réglages `EMAIL_*`.

Le dossier des photos (`DJANGO_MEDIA_ROOT`) et celui des sauvegardes doivent être sur un disque
permanent. Sur certains hébergeurs, le disque est effacé à chaque mise à jour : il faut alors
ajouter un « disque persistant ».

## Être alerté si le site tombe (point 17)

1. Créer un compte gratuit sur un service de surveillance (par exemple UptimeRobot ou Better Stack).
2. Ajouter une surveillance « HTTP » de l'adresse `https://votre-site/sante/`, toutes les 5 minutes,
   avec le mot-clé `"ok"`.
3. Choisir qui est prévenu : e-mail, SMS ou application sur le téléphone.

L'adresse `/sante/` répond 200 quand tout va bien et 503 quand la base ou la mémoire du site ne
répondent plus. Elle ne montre aucune donnée de l'école et n'est jamais limitée.

## Sauvegardes (point 20)

```bash
python manage.py sauvegarder                 # crée sauvegardes/nenuphars-AAAAMMJJ-HHMMSS.zip et le vérifie
python manage.py verifier_sauvegarde         # restaure la dernière dans une base à part et compare tout
```

- `sauvegarder` garde les 30 dernières (`--garder 60` pour en garder plus). Chaque sauvegarde est
  restaurée dans une base d'essai : si une ligne ou une photo manque, la commande échoue.
- À programmer chaque nuit (tâche « cron » de l'hébergeur), par exemple à 2 h :
  `0 2 * * * cd /chemin/du/site && python manage.py sauvegarder`.
- Une sauvegarde gardée seulement sur le serveur disparaît avec lui : copier aussi le dossier
  `sauvegardes/` ailleurs (Google Drive, clé USB du secrétariat...). Il contient les données et
  les photos des enfants : ne jamais le mettre sur GitHub ni dans un dossier public.

**Restaurer après une panne, ou chez un nouvel hébergeur :**

1. Créer une base neuve et vide, et régler les variables `DB_*` dessus.
2. `python manage.py restaurer_sauvegarde sauvegardes/nenuphars-AAAAMMJJ-HHMMSS.zip`

La commande refuse de toucher une base qui contient déjà des comptes ou des élèves. Elle fait
d'abord un essai à part ; elle ne remplit la vraie base que si l'essai est complet.

## Tester avec plusieurs visiteurs (point 19)

Sur une copie du site, jamais sur le site des familles pendant les cours :

```bash
DJANGO_LIMITE_PAGES_PAR_MINUTE=100000 gunicorn gestion_ecole.wsgi --workers 3   # dans un terminal
python outils/test_charge.py http://127.0.0.1:8000 --visiteurs 30 --duree 60 \
       --compte secretaire:secretaire123 --compte prof:prof123                  # dans un autre
```

Sans `DJANGO_LIMITE_PAGES_PAR_MINUTE`, la limite du point 01 répond « 429 » puisque tous les
visiteurs du test viennent de la même adresse : c'est la protection qui fonctionne. De même, un
compte connecté plus de 10 fois en 5 minutes est bloqué un moment.
