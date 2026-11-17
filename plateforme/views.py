# plateforme/views.py
# Pages de la plateforme, à l'adresse principale (SAAS_DOMAINE) : réservées aux
# administrateurs de la plateforme (comptes « superuser » de la base « default »,
# créés avec « python manage.py createsuperuser »).
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .creation import CreationImpossible, creer_ecole
from .forms import ConnexionForm, EcoleForm, NouvelleEcoleForm
from .models import Ecole


def admin_plateforme(vue):
    @wraps(vue)
    def verifiee(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse_lazy('plateforme:connexion')}?next={request.path}")
        if not request.user.is_superuser:
            raise PermissionDenied
        return vue(request, *args, **kwargs)
    return verifiee


def adresse_de(ecole):
    return f"https://{ecole.sous_domaine}.{settings.SAAS_DOMAINE}/"


def accueil(request):
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect("plateforme:ecoles")
    return render(request, "plateforme/accueil.html")


class ConnexionView(auth_views.LoginView):
    template_name = "plateforme/connexion.html"
    authentication_form = ConnexionForm
    redirect_authenticated_user = True
    next_page = reverse_lazy("plateforme:ecoles")


class DeconnexionView(auth_views.LogoutView):
    next_page = reverse_lazy("plateforme:accueil")


@admin_plateforme
def liste(request):
    toutes = list(Ecole.objects.using("default").all())
    for ecole in toutes:
        ecole.adresse_site = adresse_de(ecole)
    return render(request, "plateforme/ecole_liste.html", {
        "ecoles": toutes, "nb_actives": sum(e.active for e in toutes), "domaine": settings.SAAS_DOMAINE,
    })


@admin_plateforme
def nouvelle(request):
    form = NouvelleEcoleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        donnees = form.cleaned_data
        try:
            ecole, compte, mot_de_passe = creer_ecole(
                form.save(commit=False), donnees["responsable_prenom"], donnees["responsable_nom"],
                donnees["responsable_telephone"], donnees["responsable_email"])
        except CreationImpossible as erreur:
            form.add_error(None, str(erreur))
        else:
            # Le mot de passe provisoire n'est montré qu'une fois et n'est gardé nulle part en clair
            return render(request, "plateforme/ecole_creee.html", {
                "fiche": ecole, "compte": compte, "mot_de_passe": mot_de_passe, "adresse": adresse_de(ecole),
            })
    return render(request, "plateforme/ecole_form.html", {
        "form": form, "titre": "Nouvelle école", "domaine": settings.SAAS_DOMAINE,
    })


@admin_plateforme
def modifier(request, pk):
    ecole = get_object_or_404(Ecole.objects.using("default"), pk=pk)
    form = EcoleForm(request.POST or None, instance=ecole)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{ecole.nom} : informations enregistrées.")
        return redirect("plateforme:ecoles")
    return render(request, "plateforme/ecole_form.html", {
        "form": form, "titre": ecole.nom, "fiche": ecole, "adresse": adresse_de(ecole),
        "domaine": settings.SAAS_DOMAINE,
    })


@admin_plateforme
@require_POST
def changer_etat(request, pk):
    ecole = get_object_or_404(Ecole.objects.using("default"), pk=pk)
    ecole.active = not ecole.active
    ecole.save(update_fields=["active"])
    if ecole.active:
        messages.success(request, f"{ecole.nom} est de nouveau ouverte.")
    else:
        messages.success(request, f"{ecole.nom} est suspendue : ses pages affichent « Service suspendu ». "
                                  "Aucune donnée n'est effacée.")
    return redirect("plateforme:ecoles")
