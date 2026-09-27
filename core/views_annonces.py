# core/views_annonces.py
# Annonces aux parents : le secrétariat et la directrice en chef écrivent à
# toute l'école, une section ou une classe ; la direction d'une section, à sa
# section ou à l'une de ses classes. Les parents voient les annonces qui
# concernent leurs enfants.
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AnnonceForm
from .models import Annonce
from .roles import acces_requis, portee, section_de


def visibles(user, ecriture=False):
    annonces = Annonce.objects.select_related("section", "classe", "classe__section", "auteur")
    if portee(user, "annonces", ecriture) == "tout":
        return annonces
    section = section_de(user)
    if section is None:
        return annonces.none()
    ma_section = Q(section=section) | Q(classe__section=section)
    if ecriture:
        return annonces.filter(ma_section)
    return annonces.filter(ma_section | Q(section__isnull=True, classe__isnull=True))


@acces_requis("annonces")
def annonce_liste(request):
    annonces = list(visibles(request.user))
    modifiables = set(visibles(request.user, ecriture=True).values_list("pk", flat=True)) \
        if portee(request.user, "annonces", ecriture=True) else set()
    for annonce in annonces:
        annonce.modifiable = annonce.pk in modifiables
    return render(request, "core/annonce_liste.html", {"annonces": annonces})


@acces_requis("annonces", ecriture=True)
def annonce_creer(request):
    form = AnnonceForm(request.POST or None, user=request.user)
    if form.is_valid():
        annonce = form.save(commit=False)
        annonce.auteur = request.user
        annonce.save()
        messages.success(request, f"Annonce publiée. {annonce.destinataires} la voient dans leur espace.")
        return redirect("core:annonce_liste")
    return render(request, "core/generic_form.html", {"form": form, "titre": "Nouvelle annonce", "icone_titre": "annonces"})


@acces_requis("annonces", ecriture=True)
def annonce_modifier(request, pk):
    annonce = get_object_or_404(visibles(request.user, ecriture=True), pk=pk)
    form = AnnonceForm(request.POST or None, instance=annonce, user=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, "Annonce modifiée.")
        return redirect("core:annonce_liste")
    return render(request, "core/generic_form.html", {"form": form, "titre": "Modifier l'annonce", "icone_titre": "annonces"})


@acces_requis("annonces", ecriture=True)
def annonce_supprimer(request, pk):
    annonce = get_object_or_404(visibles(request.user, ecriture=True), pk=pk)
    if request.method == "POST":
        annonce.delete()
        messages.success(request, "Annonce supprimée.")
        return redirect("core:annonce_liste")
    return render(request, "core/confirm_delete.html", {"objet": annonce, "retour": "core:annonce_liste"})
