# Système de Gestion Scolaire — Institution Les Nénuphars

Aplikasyon Django konplè pou jesyon lekòl la: Élèves, Classes, Professeurs,
Employés, Paiements ak Notes. Gen tout klas yo, de **1ère Année Kindergarten
rive NS4**.

## Enstalasyon rapid

```bash
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_data      # kreye tout klas yo + kont admin + kèk done egzanp
python manage.py runserver
```

Louvri http://127.0.0.1:8000/login/ → **admin / admin123**

⚠️ Chanje mo de pas admin default la anvan w mete sistèm nan an sèvis.

## Estrikti pwojè a

```
gestion_ecole/            → paramèt Django (settings.py, urls.py)
core/
    models.py             → Utilisateur, Classe, Eleve, Professeur, Employe, Paiement, Note
    choices.py            → non lekòl la, tout klas yo (Kinder→NS4), matyè, pòs, tip peman
    forms.py              → fòm + validasyon
    views.py              → login, dashboard, CRUD chak seksyon
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
