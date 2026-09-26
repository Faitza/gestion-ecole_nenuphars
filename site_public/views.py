# site_public/views.py
# Pages publiques de l'école : ouvertes à tous, sans connexion.
from django.contrib import messages
from django.shortcuts import redirect, render

from core import choices
from core.classes import par_section
from core.models import Classe, Employe, Preinscription

from . import contenu
from .forms import MessageContactForm, PreinscriptionPubliqueForm

SESSION_DOSSIER = "preinscription_envoyee"


def _sections():
    """[{section, classes, niveaux, texte}] pour l'accueil et la page Niveaux."""
    resultat = []
    for section, classes in par_section(Classe.objects.select_related("section")):
        if section is None:
            continue
        textes = contenu.SECTIONS.get(section.nom, {})
        resultat.append({"section": section, "classes": classes, **textes})
    return resultat


def accueil(request):
    return render(request, "site_public/accueil.html", {
        "sections": _sections(),
        "nb_classes": Classe.objects.count(),
        "nb_matieres": len([m for m in choices.MATIERES if m != "Autre"]),
        "nb_bulletins": len(choices.PERIODES),
        "annee": choices.annee_scolaire_courante(),
    })


# Une direction pour toute l'école, puis une par section (poste de la fiche Employé)
ORGANISATION = [
    (choices.POSTE_DIRECTION_GENERALE, "Directrice en chef", "Toute l'école", "Veille sur les trois sections et sur la vie de l'école."),
    (choices.POSTES_DIRECTION_SECTION[0], "Directrice du Kindergarten", choices.SECTION_KINDERGARTEN, None),
    (choices.POSTES_DIRECTION_SECTION[1], "Directrice du primaire", choices.SECTION_PRIMAIRE, None),
    (choices.POSTES_DIRECTION_SECTION[2], "Directeur pédagogique du secondaire", choices.SECTION_SECONDAIRE, None),
]


def ecole(request):
    personnes = {}
    for employe in Employe.objects.filter(poste__in=[poste for poste, *_ in ORGANISATION]).order_by("nom"):
        personnes.setdefault(employe.poste, employe)
    organisation = [
        {"titre": titre, "perimetre": perimetre, "personne": personnes.get(poste),
         "texte": texte or contenu.SECTIONS.get(perimetre, {}).get("niveaux", "")}
        for poste, titre, perimetre, texte in ORGANISATION
    ]
    return render(request, "site_public/ecole.html", {"organisation": organisation})


def niveaux(request):
    return render(request, "site_public/niveaux.html", {
        "sections": _sections(),
        "matieres": [m for m in choices.MATIERES if m != "Autre"],
        "periodes": choices.PERIODES,
    })


def admissions(request):
    return render(request, "site_public/admissions.html", {"annee": choices.annee_scolaire_courante()})


def preinscription(request):
    form = PreinscriptionPubliqueForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if form.est_un_robot:
            return redirect("site:preinscription_envoyee")
        if form.is_valid():
            dossier = form.save()
            # La page suivante affiche le numéro de dossier, à cette famille seulement
            request.session[SESSION_DOSSIER] = dossier.pk
            return redirect("site:preinscription_envoyee")
    return render(request, "site_public/preinscription.html", {"form": form, "annee": choices.annee_scolaire_courante()})


def preinscription_envoyee(request):
    dossier = Preinscription.objects.select_related("classe_demandee").filter(pk=request.session.get(SESSION_DOSSIER)).first()
    return render(request, "site_public/preinscription_envoyee.html", {"dossier": dossier})


def contact(request):
    form = MessageContactForm(request.POST or None)
    if request.method == "POST":
        if form.est_un_robot or form.is_valid():
            if not form.est_un_robot:
                form.save()
            messages.success(request, "Merci, votre message a bien été envoyé. Le secrétariat vous répondra rapidement.")
            return redirect("site:contact")
    return render(request, "site_public/contact.html", {"form": form})
