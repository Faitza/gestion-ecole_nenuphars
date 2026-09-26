# Horaires par défaut du secondaire, repris de la maquette (5 heures de 55 minutes
# et une récréation). La direction de la section peut les changer dans l'administration.
import datetime

from django.db import migrations

CRENEAUX_SECONDAIRE = [
    ("1re heure", (7, 30), (8, 25), True),
    ("2e heure", (8, 25), (9, 20), True),
    ("Récréation", (9, 20), (9, 40), False),
    ("3e heure", (9, 40), (10, 35), True),
    ("4e heure", (10, 35), (11, 30), True),
    ("5e heure", (11, 30), (12, 25), True),
]


def creer(apps, schema_editor):
    Section = apps.get_model("core", "Section")
    Creneau = apps.get_model("core", "Creneau")
    secondaire = Section.objects.filter(nom="Secondaire").first()
    if secondaire is None or Creneau.objects.filter(section=secondaire).exists():
        return
    for nom, debut, fin, est_un_cours in CRENEAUX_SECONDAIRE:
        Creneau.objects.create(
            section=secondaire, nom=nom, est_un_cours=est_un_cours,
            heure_debut=datetime.time(*debut), heure_fin=datetime.time(*fin),
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_professeurs_affectations_cours"),
    ]

    operations = [
        migrations.RunPython(creer, migrations.RunPython.noop),
    ]
