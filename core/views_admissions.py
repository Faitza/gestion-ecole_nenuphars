# core/views_admissions.py
# Préinscriptions envoyées depuis le site public, de la demande à
# l'inscription : le secrétariat vérifie le dossier et le transmet, la
# direction de la section accepte ou refuse, puis le secrétariat inscrit
# l'élève (sa fiche est créée dans la classe demandée). Aussi : les messages
# de la page Contact.
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import choices
from .forms import PreinscriptionGestionForm
from .models import Eleve, MessageContact, Preinscription
from .roles import acces_requis, filtrer, peut, peut_decider_preinscription

EN_COURS = "en-cours"
TOUTES = "toutes"


def _visibles(user):
    """Les dossiers de toute l'école (secrétariat) ou de sa section (direction)."""
    return filtrer(user, "preinscriptions",
                   Preinscription.objects.select_related("classe_demandee", "classe_demandee__section", "eleve"))


def actions_possibles(user, dossier):
    """[(action, libellé, icône)] : ce que cet utilisateur peut faire du dossier à son étape."""
    actions = []
    secretariat = peut(user, "preinscriptions", ecriture=True)
    if dossier.etape == choices.ETAPE_RECUE and secretariat:
        actions.append(("transmettre", "Transmettre à la direction", "suivant"))
    if dossier.etape != choices.ETAPE_INSCRITE and peut_decider_preinscription(user, dossier):
        if dossier.etape != choices.ETAPE_ACCEPTEE:
            actions.append(("accepter", "Accepter", "valider"))
        if dossier.etape != choices.ETAPE_REFUSEE:
            actions.append(("refuser", "Refuser", "refuser"))
    if dossier.etape == choices.ETAPE_ACCEPTEE and secretariat and peut(user, "eleves", ecriture=True):
        actions.append(("inscrire", "Inscrire l'élève", "inscrire"))
    return actions


@acces_requis("preinscriptions")
def preinscription_liste(request):
    visibles = _visibles(request.user)
    filtre = request.GET.get("etape") or EN_COURS
    q = request.GET.get("q", "").strip()

    dossiers = visibles
    if filtre == EN_COURS:
        dossiers = dossiers.filter(etape__in=choices.ETAPES_EN_COURS)
    elif filtre in choices.ETAPES_PREINSCRIPTION:
        dossiers = dossiers.filter(etape=filtre)
    if q:
        dossiers = dossiers.filter(Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(numero__icontains=q)
                                   | Q(nom_parent__icontains=q) | Q(telephone_parent__icontains=q))
    dossiers = list(dossiers)
    for dossier in dossiers:
        dossier.actions = actions_possibles(request.user, dossier)

    nombres = dict(visibles.order_by().values_list("etape").annotate(n=Count("pk")))
    onglets = [(EN_COURS, "À traiter", sum(nombres.get(e, 0) for e in choices.ETAPES_EN_COURS))]
    onglets += [(etape, etape, nombres.get(etape, 0)) for etape in choices.ETAPES_PREINSCRIPTION]
    onglets.append((TOUTES, "Toutes", sum(nombres.values())))
    return render(request, "core/preinscription_liste.html", {
        "dossiers": dossiers, "onglets": onglets, "filtre": filtre, "q": q,
    })


@acces_requis("preinscriptions")
def preinscription_fiche(request, pk):
    dossier = get_object_or_404(_visibles(request.user).select_related("decision_par"), pk=pk)
    # Même nom et prénom qu'un élève déjà inscrit : peut-être un doublon
    doublons = Eleve.objects.filter(nom__iexact=dossier.nom, prenom__iexact=dossier.prenom).select_related("classe")
    if dossier.eleve_id:
        doublons = doublons.exclude(pk=dossier.eleve_id)
    actions = actions_possibles(request.user, dossier)
    return render(request, "core/preinscription_fiche.html", {
        "dossier": dossier, "actions": actions, "etapes": choices.ETAPES_PREINSCRIPTION,
        "decide": any(action in ("accepter", "refuser") for action, _, _ in actions),
        "doublons": list(doublons) if peut(request.user, "eleves") else [],
    })


@acces_requis("preinscriptions", ecriture=True)
def preinscription_modifier(request, pk):
    dossier = get_object_or_404(_visibles(request.user), pk=pk)
    form = PreinscriptionGestionForm(request.POST or None, request.FILES or None, instance=dossier)
    if form.is_valid():
        form.save()
        messages.success(request, f"Dossier {dossier.numero} enregistré.")
        return redirect("core:preinscription_fiche", pk=dossier.pk)
    return render(request, "core/generic_form.html", {
        "form": form, "titre": f"Dossier {dossier.numero}", "icone_titre": "preinscriptions",
    })


@require_POST
@acces_requis("preinscriptions")
def preinscription_etape(request, pk):
    dossier = get_object_or_404(_visibles(request.user), pk=pk)
    action = request.POST.get("action")
    if action not in {a for a, _, _ in actions_possibles(request.user, dossier)}:
        raise PermissionDenied

    if action == "transmettre":
        dossier.etape = choices.ETAPE_CHEZ_LA_DIRECTION
        dossier.save(update_fields=["etape", "mise_a_jour"])
        messages.success(request, f"Dossier {dossier.numero} transmis à la direction ({dossier.section or 'section à préciser'}).")

    elif action in ("accepter", "refuser"):
        dossier.etape = choices.ETAPE_ACCEPTEE if action == "accepter" else choices.ETAPE_REFUSEE
        dossier.avis_direction = request.POST.get("avis", "").strip()
        dossier.decision_par, dossier.decision_le = request.user, timezone.now()
        dossier.save(update_fields=["etape", "avis_direction", "decision_par", "decision_le", "mise_a_jour"])
        if action == "accepter":
            messages.success(request, f"Demande acceptée. Le secrétariat peut maintenant inscrire {dossier.prenom} {dossier.nom}.")
        else:
            messages.success(request, f"Demande {dossier.numero} refusée.")

    elif action == "inscrire":
        if dossier.classe_demandee is None:
            messages.error(request, "Choisissez d'abord la classe demandée (bouton Modifier).")
            return redirect("core:preinscription_fiche", pk=dossier.pk)
        eleve = _inscrire(dossier)
        messages.success(request, f"{eleve.prenom} {eleve.nom} est inscrit(e) en {eleve.classe}. "
                                  "La famille règle les frais d'inscription à la caisse.")
        return redirect("core:eleve_fiche", pk=eleve.pk)

    return redirect("core:preinscription_fiche", pk=dossier.pk)


def _inscrire(dossier):
    """Crée la fiche de l'élève dans la classe demandée, avec la photo du dossier."""
    with transaction.atomic():
        eleve = Eleve(
            nom=dossier.nom, prenom=dossier.prenom, date_naissance=dossier.date_naissance, genre=dossier.genre,
            classe=dossier.classe_demandee, nom_parent_tuteur=dossier.nom_parent,
            telephone_parent=dossier.telephone_parent, email=dossier.email_parent or None, adresse=dossier.adresse,
        )
        if dossier.photo:
            try:
                with dossier.photo.open("rb") as fichier:
                    eleve.photo.save("photo.jpg", ContentFile(fichier.read()), save=False)
            except FileNotFoundError:
                pass  # photo perdue sur le disque : l'élève est inscrit sans photo
        eleve.save()
        dossier.eleve, dossier.etape = eleve, choices.ETAPE_INSCRITE
        dossier.save(update_fields=["eleve", "etape", "mise_a_jour"])
    return eleve


@acces_requis("preinscriptions", ecriture=True)
def preinscription_supprimer(request, pk):
    dossier = get_object_or_404(_visibles(request.user), pk=pk)
    if request.method == "POST":
        dossier.delete()
        messages.success(request, f"Dossier {dossier.numero} supprimé.")
        return redirect("core:preinscription_liste")
    return render(request, "core/confirm_delete.html", {"objet": dossier, "retour": "core:preinscription_liste"})


PIECES = {"acte_naissance", "dernier_bulletin"}


@acces_requis("preinscriptions")
def piece(request, pk, champ):
    """Acte de naissance ou bulletin joint au dossier, seulement pour ceux qui voient le dossier."""
    dossier = get_object_or_404(_visibles(request.user), pk=pk)
    fichier = getattr(dossier, champ) if champ in PIECES else None
    if not fichier:
        raise Http404
    try:
        contenu = fichier.open("rb")
    except FileNotFoundError:
        raise Http404
    if fichier.name.endswith(".pdf"):
        # Un PDF envoyé par un inconnu est téléchargé, pas ouvert dans la page
        return FileResponse(contenu, as_attachment=True, filename=f"{dossier.numero}-{champ}.pdf",
                            content_type="application/pdf")
    reponse = FileResponse(contenu, content_type="image/jpeg")
    reponse["Cache-Control"] = "private, max-age=3600"
    return reponse


# ─────────────────────────── Messages de la page Contact ───────────────────────────
@acces_requis("messages_site")
def message_liste(request):
    tous = request.GET.get("voir") == "tous"
    liste = MessageContact.objects.select_related("traite_par")
    if not tous:
        liste = liste.filter(traite=False)
    return render(request, "core/message_liste.html", {
        "liste": liste, "tous": tous, "nb_a_traiter": MessageContact.objects.filter(traite=False).count(),
    })


@require_POST
@acces_requis("messages_site", ecriture=True)
def message_traite(request, pk):
    message = get_object_or_404(MessageContact, pk=pk)
    message.traite = not message.traite
    message.traite_par, message.traite_le = (request.user, timezone.now()) if message.traite else (None, None)
    message.save(update_fields=["traite", "traite_par", "traite_le"])
    liste = reverse("core:message_liste")
    return redirect(f"{liste}?voir=tous" if request.POST.get("voir") == "tous" else liste)
