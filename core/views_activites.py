# core/views_activites.py
# Activités de l'école (concours Génies en herbe, sorties, fêtes...) : le
# secrétariat les écrit et ajoute les photos depuis son téléphone ; elles
# paraissent sur la page « Activités » du site public.
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ActiviteForm
from .models import Activite, PhotoActivite
from .roles import acces_requis


@acces_requis("activites")
def activite_liste(request):
    activites = Activite.objects.prefetch_related("photos")
    return render(request, "core/activite_liste.html", {"activites": activites})


@acces_requis("activites", ecriture=True)
def activite_creer(request):
    form = ActiviteForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.instance.cree_par = request.user
        activite = form.save()
        nb = len(form.cleaned_data["photos"])
        messages.success(request, f"Activité enregistrée avec {nb} photo{'s' if nb > 1 else ''}."
                         + (" Elle est sur le site de l'école." if activite.publiee else ""))
        return redirect("core:activite_modifier", pk=activite.pk)
    return render(request, "core/activite_form.html", {"form": form, "titre": "Nouvelle activité"})


@acces_requis("activites", ecriture=True)
def activite_modifier(request, pk):
    activite = get_object_or_404(Activite, pk=pk)
    form = ActiviteForm(request.POST or None, request.FILES or None, instance=activite)
    if form.is_valid():
        form.save()
        messages.success(request, "Activité enregistrée.")
        return redirect("core:activite_modifier", pk=activite.pk)
    return render(request, "core/activite_form.html", {
        "form": form, "titre": "Modifier l'activité", "activite": activite, "photos": activite.photos.all(),
    })


@require_POST
@acces_requis("activites", ecriture=True)
def activite_photo_supprimer(request, pk):
    photo = get_object_or_404(PhotoActivite, pk=pk)
    photo.delete()
    messages.success(request, "Photo retirée.")
    return redirect("core:activite_modifier", pk=photo.activite_id)


@acces_requis("activites", ecriture=True)
def activite_supprimer(request, pk):
    activite = get_object_or_404(Activite, pk=pk)
    if request.method == "POST":
        activite.delete()
        messages.success(request, "Activité supprimée, avec ses photos.")
        return redirect("core:activite_liste")
    return render(request, "core/confirm_delete.html", {"objet": activite, "retour": "core:activite_liste"})
