# Système de Gestion Scolaire — Institution Les Nénuphars

Aplikasyon Django konplè pou jesyon lekòl la: Élèves, Classes, Professeurs,
Employés, Paiements ak Notes. Gen tout klas yo, de **1ère Année Kindergarten
rive NS4**.

## Enstalasyon rapid

```bash
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # Windows : copy .env.example .env
python manage.py migrate        # kreye tab yo + 3 seksyon yo + wòl yo
python manage.py seed_data      # kreye tout klas yo + kont admin + kèk done egzanp
python manage.py runserver
```

Louvri http://127.0.0.1:8000/connexion/ → **admin / admin123** (pou esè sèlman)

⚠️ `seed_data` mache sèlman lè `DJANGO_DEBUG=1`. An pwodiksyon, kreye kont
direktris an chèf la ak `python manage.py createsuperuser`.

## Paramèt (fichye `.env`)

Pa gen okenn sekrè nan kòd la ankò. Tout paramèt yo nan fichye `.env`
(li pa janm monte sou GitHub). Gade `.env.example` pou lis la.

- **Devlopman**: `DJANGO_DEBUG=1` ak `DB_ENGINE=sqlite` (pa gen anyen pou enstale).
- **Pwodiksyon**: `DJANGO_DEBUG=0`, yon `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`,
  epi `DB_ENGINE=postgresql` ak `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.

## Seksyon ak wòl

- 3 seksyon: **Kindergarten** (1ère–3ème Année Kinder), **Primaire** (1ère–6ème AF),
  **Secondaire** (7ème AF–NSIV, yon sèl direktè pedagojik).
- Wòl yo se gwoup Django: Parent, Professeur, Surveillant, Censeur, Secrétariat,
  Caisse, Direction de section, Directrice en chef. Dwa chak wòl nan `core/roles.py`,
  menm jan ak tablo « Droits d'accès » nan kaye chaj la.
- Wòl yon anplwaye swiv pòs li: lè w konekte yon kont ak fich anplwaye a
  (chan « utilisateur »), kont lan jwenn wòl ki koresponn ak pòs la.
  Direksyon seksyon, siveyan ak sansè wè sèlman seksyon ki sou fich yo.
- Yon sèl paj koneksyon pou tout moun: telefòn, imèl oswa non itilizatè.
  Yon kont ki gen « doit changer son mot de passe » dwe chanje modpas li anvan l fè lòt bagay.

## Estrikti pwojè a

```
gestion_ecole/            → paramèt Django (settings.py, urls.py)
core/
    models.py             → Utilisateur, Section, Classe, Eleve, Professeur, Employe, Paiement, Note
    choices.py            → non lekòl la, tout klas yo (Kinder→NS4), seksyon, matyè, pòs, tip peman
    roles.py              → wòl yo ak dwa chak wòl
    backends.py           → koneksyon ak telefòn, imèl oswa non itilizatè
    forms.py              → fòm + validasyon
    views.py              → koneksyon, espas chak moun, dashboard, CRUD chak seksyon
    tests.py              → tès otomatik (python manage.py test)
    admin.py              → jesyon done nan /admin/
    management/commands/seed_data.py → kreye tout klas yo + done egzanp
templates/core/           → tout paj HTML
static/css/style.css
```

## Pèsonalize pou lekòl ou a

- **Non lekòl / vil**: chanje `NOM_ECOLE` ak `VILLE_ECOLE` nan `core/choices.py`,
  epi nan `templates/core/login.html` ak `base.html` (tèks "LES NÉNUPHARS" / "Les Cayes")
- **Lis klas yo**: `CLASSES_PAR_DEFAUT` nan `core/choices.py` — men ou ka tou
  jere klas yo dirèkteman nan sèksyon "Classes" nan aplikasyon an (ajoute/efase
  san w pa touche kòd la)
- **Matyè, pòs anplwaye, tip peman**: tout nan `core/choices.py` tou

## Fonksyonalite

- **Élèves**: enfo elèv la + non/telefòn paran-tutè + klas (yon sèl klas pou chak elèv)
- **Classes**: kreye/modifye klas yo (non, sik: Préscolaire/Fondamentale/Secondaire, ane eskolè)
- **Professeurs**: ka anseye plizyè klas (relasyon plizyè-a-plizyè)
- **Employés**: pèsonèl ki pa anseye (sekretè, kontab, elt.)
- **Paiements**: swiv peman elèv yo (eskolarite, enskripsyon, elt.) ak total resevwa
- **Notes**: nòt pa matyè/trimès/ane eskolè, ak rechèch

## Pwochèn etap posib

- Ajoute yon bilten (relve nòt) pou chak elèv, pa trimès
- Ekspòte lis elèv/peman an PDF oswa Excel
- Deplwaye sou entènèt (Render, Railway, PythonAnywhere)
