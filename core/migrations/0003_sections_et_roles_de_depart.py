# Données de départ : les trois sections, la section de chaque classe
# existante et les groupes (rôles). Les listes sont recopiées ici pour que
# la migration reste la même si core/choices.py change plus tard.
from django.db import migrations

SECTIONS = [("Kindergarten", 1), ("Primaire", 2), ("Secondaire", 3)]

SECTION_PAR_CLASSE = {
    "1ère Année Kinder": "Kindergarten",
    "2ème Année Kinder": "Kindergarten",
    "3ème Année Kinder": "Kindergarten",
    "1ère AF": "Primaire",
    "2ème AF": "Primaire",
    "3ème AF": "Primaire",
    "4ème AF": "Primaire",
    "5ème AF": "Primaire",
    "6ème AF": "Primaire",
    "7ème AF": "Secondaire",
    "8ème AF": "Secondaire",
    "9ème AF": "Secondaire",
    "NSI": "Secondaire",
    "NSII": "Secondaire",
    "NSIII": "Secondaire",
    "NSIV": "Secondaire",
}

ROLES = [
    "Parent", "Professeur", "Surveillant", "Censeur", "Secrétariat",
    "Caisse", "Direction de section", "Directrice en chef",
]


def creer(apps, schema_editor):
    Section = apps.get_model("core", "Section")
    Classe = apps.get_model("core", "Classe")
    Employe = apps.get_model("core", "Employe")
    Group = apps.get_model("auth", "Group")

    sections = {}
    for nom, ordre in SECTIONS:
        sections[nom], _ = Section.objects.get_or_create(nom=nom, defaults={"ordre": ordre})

    for classe in Classe.objects.filter(section__isnull=True):
        nom_section = SECTION_PAR_CLASSE.get(classe.nom)
        if nom_section:
            classe.section = sections[nom_section]
            classe.save(update_fields=["section"])

    for nom in ROLES:
        Group.objects.get_or_create(name=nom)

    # L'ancien poste « Directeur(trice) » est celui de la direction générale
    Employe.objects.filter(poste="Directeur(trice)").update(poste="Directeur(trice) en chef")


def annuler(apps, schema_editor):
    Employe = apps.get_model("core", "Employe")
    Employe.objects.filter(poste="Directeur(trice) en chef").update(poste="Directeur(trice)")
    # Les groupes restent ; les sections disparaissent avec leur table si 0002 est aussi annulée.


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("core", "0002_sections_roles_comptes"),
    ]

    operations = [
        migrations.RunPython(creer, annuler),
    ]
