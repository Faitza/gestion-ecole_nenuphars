# site_public/views.py
# Pages publiques de l'école : ouvertes à tous, sans connexion.
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from core import choices, roles
from core.classes import par_section
from core.models import Activite, Classe, Employe, PhotoActivite, Preinscription

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
        "activites": Activite.objects.filter(publiee=True).prefetch_related("photos")[:3],
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


# ─────────────────────────── Activités et concours ───────────────────────────
def activites(request):
    liste = Activite.objects.filter(publiee=True).prefetch_related("photos")
    categorie = request.GET.get("type", "")
    if categorie in choices.CATEGORIES_ACTIVITE:
        liste = liste.filter(categorie=categorie)
    else:
        categorie = ""
    presentes = set(Activite.objects.filter(publiee=True).values_list("categorie", flat=True))
    return render(request, "site_public/activites.html", {
        "activites": liste, "categorie": categorie,
        "categories": [c for c in choices.CATEGORIES_ACTIVITE if c in presentes],
    })


def activite(request, pk):
    activite = get_object_or_404(Activite.objects.filter(publiee=True), pk=pk)
    return render(request, "site_public/activite.html", {
        "activite": activite, "photos": activite.photos.all(),
        "autres": Activite.objects.filter(publiee=True).exclude(pk=pk).prefetch_related("photos")[:3],
    })


def photo_activite(request, pk, taille):
    """Les photos des activités publiées sont pour tout le monde ; les autres, pour le secrétariat seulement."""
    if taille not in ("grande", "vignette"):
        raise Http404
    photo = get_object_or_404(PhotoActivite.objects.select_related("activite"), pk=pk)
    publique = photo.activite.publiee
    if not publique and not (request.user.is_authenticated and roles.peut(request.user, "activites")):
        raise Http404
    champ = photo.image if taille == "grande" else photo.vignette
    try:
        fichier = champ.open("rb")
    except (FileNotFoundError, ValueError):
        raise Http404
    reponse = FileResponse(fichier, content_type="image/jpeg")
    reponse["Cache-Control"] = "public, max-age=3600" if publique else "private, no-store"
    return reponse
