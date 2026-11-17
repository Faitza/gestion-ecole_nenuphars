# Plusieurs écoles sur le même site (SaaS)

Le même site peut servir plusieurs écoles. Chaque école a **sa propre adresse** et **sa propre
base de données** : ses élèves, notes, paiements, comptes et photos ne sont jamais mélangés
avec ceux d'une autre école.

| Adresse | Ce qu'on y trouve |
|---------|-------------------|
| `ekol.ht` | La plateforme : liste des écoles, création, suspension (administrateurs seulement) |
| `nenuphars.ekol.ht` | Le site public et la gestion de l'Institution Les Nénuphars |
| `stjoseph.ekol.ht` | Le site public et la gestion du Collège Saint-Joseph |

`ekol.ht` est un exemple : choisissez votre nom de domaine.

Sans le réglage `SAAS_DOMAINE`, rien ne change : le site sert une seule école, comme avant.

## Comment c'est séparé

- **Base de données** : une base par école (`ecole_nenuphars`, `ecole_stjoseph`...). La plateforme
  garde seulement la liste des écoles dans sa base (« default »). Chaque requête va vers la base
  de l'école de l'adresse (`plateforme/routeur.py`).
- **Comptes** : un compte n'existe que dans son école. Le même numéro de téléphone peut avoir un
  compte dans deux écoles, avec deux mots de passe différents. Une session ouverte dans une école ne
  vaut rien dans une autre.
- **Photos et pièces jointes** : dans `DJANGO_MEDIA_ROOT/ecoles/<adresse>/`.
- **Mémoire du site (cache)** : clés propres à chaque école (compteurs de requêtes, sections du site public).
- **Sauvegardes** : une par école, dans `sauvegardes/<adresse>/`.

Les tests `plateforme/tests.py` vérifient cette séparation (élèves, comptes, sessions, photos,
mémoire, sauvegardes).

## Mettre en ligne

1. **Nom de domaine** : acheter le domaine, puis créer chez le fournisseur du domaine deux
   enregistrements DNS vers le serveur : `ekol.ht` et `*.ekol.ht` (le « joker » couvre toutes les écoles).
2. **Certificat https** : il doit couvrir `ekol.ht` et `*.ekol.ht` (certificat « wildcard »). La plupart
   des hébergeurs (Render, Railway, Cloudflare...) le font tout seuls quand on ajoute le domaine joker.
3. **Réglages** chez l'hébergeur, en plus de ceux de `docs/production.md` :
   ```
   SAAS_DOMAINE=ekol.ht
   SAAS_NOM=Ekol.ht
   ```
   `DJANGO_ALLOWED_HOSTS` et `DJANGO_CSRF_TRUSTED_ORIGINS` acceptent alors automatiquement
   `ekol.ht` et toutes ses sous-adresses.
4. **Base de données** : avec PostgreSQL (conseillé), l'utilisateur `DB_USER` doit avoir le droit de
   créer des bases (`ALTER USER ... CREATEDB;`), car chaque nouvelle école reçoit sa base.
   Avec SQLite, les bases sont dans `DJANGO_DOSSIER_BASES_ECOLES`, sur un disque permanent.
5. **Démarrage** : `migrer_ecoles` remplace `migrate` (il met à jour la plateforme et toutes les écoles) :
   ```bash
   pip install -r requirements.txt
   python manage.py migrer_ecoles
   python manage.py collectstatic --noinput
   gunicorn gestion_ecole.wsgi --workers 3 --timeout 120
   ```
6. **Premier administrateur de la plateforme** (une seule fois) :
   ```bash
   python manage.py createsuperuser
   ```

## Ouvrir une école

Sur `ekol.ht`, « Espace administrateur de la plateforme », puis **+ Nouvelle école** : nom, adresse
(ex. `stjoseph`), ville, coordonnées, et le (la) responsable. Le site crée la base de l'école avec les
sections, les rôles et les horaires de départ, puis le compte « Directrice en chef » du (de la)
responsable. Un mot de passe provisoire s'affiche **une seule fois** ; il est changé à la première
connexion. Le (la) responsable crée ensuite les comptes du personnel comme avant.

En ligne de commande, même chose :

```bash
python manage.py creer_ecole stjoseph "Collège Saint-Joseph" --ville Jacmel \
    --telephone "3712 3456" --prenom Jean --nom Louis
```

**Suspendre** une école (bouton « Suspendre ») affiche « Service suspendu » à son adresse. Rien n'est
effacé ; « Rouvrir » la remet en service.

## Passer Les Nénuphars (déjà en ligne seule) sur la plateforme

1. Avant de changer les réglages, faire une sauvegarde vérifiée : `python manage.py sauvegarder`.
2. Ajouter `SAAS_DOMAINE`, puis `python manage.py migrer_ecoles`.
3. Créer l'école sans compte et y remettre la sauvegarde (comptes, élèves, photos) :
   ```bash
   python manage.py creer_ecole nenuphars "Institution Les Nénuphars" --nom-court "Les Nénuphars" \
       --ville "Les Cayes" --sans-compte
   python manage.py ecole nenuphars restaurer_sauvegarde sauvegardes/nenuphars-AAAAMMJJ-HHMMSS.zip
   ```
4. Les familles utilisent ensuite `nenuphars.ekol.ht`. Pour garder l'ancienne adresse
   (`lesnenuphars.ht`), la faire rediriger vers la nouvelle chez le fournisseur du domaine.

Les textes détaillés de `site_public/contenu.py` (histoire, mot de la directrice, frais...) restent ceux
des Nénuphars en mode « une seule école ». Sur la plateforme, chaque école remplit ses coordonnées,
son accroche et sa présentation dans sa fiche (bouton « Modifier »).

## Commandes pour une école

Toutes les commandes habituelles se lancent pour une école avec `ecole <adresse>`, ou pour toutes
avec `ecole --toutes` :

```bash
python manage.py ecole nenuphars sauvegarder        # sauvegarde vérifiée de cette école
python manage.py ecole --toutes sauvegarder         # chaque nuit : toutes les écoles
python manage.py ecole stjoseph verifier_sauvegarde
python manage.py ecole stjoseph createsuperuser     # compte /admin/ de cette école seulement
```

## Ce qui viendra ensuite

- Abonnements et paiement des écoles (MonCash, carte...) ; une école en retard de paiement peut
  déjà être suspendue à la main.
- Logo et couleurs propres à chaque école ; la fiche de l'école modifiable par sa directrice.
- Nom de domaine propre à une école (ex. `stjoseph.edu.ht`) en plus de son adresse sur la plateforme.
