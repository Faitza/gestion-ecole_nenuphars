# core/views.py
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Q
from django.urls import reverse_lazy

from .models import Eleve, Professeur, Employe, Paiement, Note, Classe
from .forms import LoginForm, EleveForm, ProfesseurForm, EmployeForm, PaiementForm, NoteForm, ClasseForm, MotDePasseForm
from .roles import acces_requis, filtrer, peut, roles_de, utilise_la_gestion
from . import anniversaires, choices, professeurs
from .views_professeurs import espace_professeur


class LoginView(auth_views.LoginView):
    template_name = "core/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        reponse = super().form_valid(form)
        # Petite fenêtre « Bienvenue » sur la première page après la connexion
        messages.success(self.request, anniversaires.message_de_bienvenue(self.request.user), extra_tags="bienvenue")
        return reponse


class LogoutView(auth_views.LogoutView):
    next_page = "core:login"


class MotDePasseView(auth_views.PasswordChangeView):
    """Changement du mot de passe (obligatoire après un mot de passe provisoire)."""
    template_name = "core/mot_de_passe.html"
    form_class = MotDePasseForm
    success_url = reverse_lazy("core:espace")

    def form_valid(self, form):
        reponse = super().form_valid(form)
        if self.request.user.doit_changer_mot_de_passe:
            self.request.user.doit_changer_mot_de_passe = False
            self.request.user.save(update_fields=["doit_changer_mot_de_passe"])
        messages.success(self.request, "Mot de passe changé.")
        return reponse


@login_required
def espace(request):
    """Après la connexion, chacun est envoyé vers son propre espace."""
    if utilise_la_gestion(request.user):
        return redirect("core:dashboard")
    professeur = getattr(request.user, "professeur", None)
    if professeur is not None:
        return espace_professeur(request, professeur)
    return render(request, "core/espace_a_venir.html", {"roles": sorted(roles_de(request.user))})


@login_required
def dashboard(request):
    user = request.user
    if not utilise_la_gestion(user):
        return redirect("core:espace")
    context = {
        "nb_eleves": filtrer(user, "eleves", Eleve.objects.all()).count() if peut(user, "eleves") else None,
        "nb_professeurs": filtrer(user, "professeurs", Professeur.objects.all()).count() if peut(user, "professeurs") else None,
        "nb_employes": filtrer(user, "employes", Employe.objects.all()).count() if peut(user, "employes") else None,
        "revenus": None,
    }
    if peut(user, "paiements"):
        paiements = filtrer(user, "paiements", Paiement.objects.filter(statut="Payé"))
        context["revenus"] = paiements.aggregate(total=Sum("montant"))["total"] or 0
    if peut(user, "notes"):
        context["dernieres_notes"] = filtrer(user, "notes", Note.objects.select_related("eleve", "professeur"))[:5]
    # Anniversaires et années à l'école du personnel que l'on peut voir, dans les 7 jours
    context["evenements"] = anniversaires.evenements(anniversaires.personnel_visible(user))
    context["jours_d_avance"] = anniversaires.JOURS_D_AVANCE
    context["prenom"] = anniversaires.prenom_de(user)
    context["aujourd_hui"] = anniversaires.aujourd_hui()
    context["ma_fete"] = anniversaires.c_est_sa_fete(anniversaires.fiche_de(user))
    return render(request, "core/dashboard.html", context)


# ─────────────────────────── ÉLÈVES ───────────────────────────
@acces_requis("eleves")
def eleve_liste(request):
    q = request.GET.get("q", "").strip()
    eleves = filtrer(request.user, "eleves", Eleve.objects.select_related("classe"))
    if q:
        eleves = eleves.filter(Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(nom_parent_tuteur__icontains=q))
    return render(request, "core/eleve_liste.html", {"eleves": eleves, "q": q})


@acces_requis("eleves", ecriture=True)
def eleve_creer(request):
    if request.method == "POST":
        form = EleveForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Élève ajouté(e) avec succès!")
            return redirect("core:eleve_liste")
    else:
        form = EleveForm()
    return render(request, "core/generic_form.html", {"form": form, "icone_titre": "ajouter", "titre": "Nouvel Élève"})


@acces_requis("eleves", ecriture=True)
def eleve_modifier(request, pk):
    eleve = get_object_or_404(filtrer(request.user, "eleves", Eleve.objects.all(), ecriture=True), pk=pk)
    if request.method == "POST":
        form = EleveForm(request.POST, instance=eleve)
        if form.is_valid():
            form.save()
            messages.success(request, "Élève modifié(e) avec succès!")
            return redirect("core:eleve_liste")
    else:
        form = EleveForm(instance=eleve)
    return render(request, "core/generic_form.html", {"form": form, "titre": "Modifier l'Élève"})


@acces_requis("eleves", ecriture=True)
def eleve_supprimer(request, pk):
    eleve = get_object_or_404(filtrer(request.user, "eleves", Eleve.objects.all(), ecriture=True), pk=pk)
    if request.method == "POST":
        eleve.delete()
        messages.success(request, "Élève supprimé(e)!")
        return redirect("core:eleve_liste")
    return render(request, "core/confirm_delete.html", {"objet": eleve, "retour": "core:eleve_liste"})


# ─────────────────────────── CLASSES ───────────────────────────
@acces_requis("classes")
def classe_liste(request):
    classes = filtrer(request.user, "classes", Classe.objects.select_related("section"))
    return render(request, "core/classe_liste.html", {"classes": classes})


@acces_requis("classes", ecriture=True)
def classe_creer(request):
    if request.method == "POST":
        form = ClasseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Classe ajoutée avec succès!")
            return redirect("core:classe_liste")
    else:
        form = ClasseForm()
    return render(request, "core/generic_form.html", {"form": form, "icone_titre": "ajouter", "titre": "Nouvelle Classe"})


@acces_requis("classes", ecriture=True)
def classe_modifier(request, pk):
    classe = get_object_or_404(filtrer(request.user, "classes", Classe.objects.all(), ecriture=True), pk=pk)
    if request.method == "POST":
        form = ClasseForm(request.POST, instance=classe)
        if form.is_valid():
            form.save()
            messages.success(request, "Classe modifiée avec succès!")
            return redirect("core:classe_liste")
    else:
        form = ClasseForm(instance=classe)
    return render(request, "core/generic_form.html", {"form": form, "titre": "Modifier la Classe"})


@acces_requis("classes", ecriture=True)
def classe_supprimer(request, pk):
    classe = get_object_or_404(filtrer(request.user, "classes", Classe.objects.all(), ecriture=True), pk=pk)
    if request.method == "POST":
        classe.delete()
        messages.success(request, "Classe supprimée!")
        return redirect("core:classe_liste")
    return render(request, "core/confirm_delete.html", {"objet": classe, "retour": "core:classe_liste"})


# ─────────────────────────── PROFESSEURS ───────────────────────────
@acces_requis("professeurs")
def professeur_liste(request):
    liste = filtrer(request.user, "professeurs", Professeur.objects.select_related("section").prefetch_related("classes"))
    return render(request, "core/professeur_liste.html", {"professeurs": liste})


@acces_requis("professeurs", ecriture=True)
def professeur_modifier(request, pk):
    professeur = get_object_or_404(filtrer(request.user, "professeurs", Professeur.objects.all(), ecriture=True), pk=pk)
    if request.method == "POST":
        form = ProfesseurForm(request.POST, instance=professeur)
        if form.is_valid():
            form.save()
            professeurs.mettre_a_jour_compte(professeur)
            messages.success(request, "Professeur modifié(e) avec succès!")
            return redirect("core:professeur_fiche", pk=professeur.pk)
    else:
        form = ProfesseurForm(instance=professeur)
    return render(request, "core/generic_form.html", {"form": form, "titre": "Modifier le Professeur"})


@acces_requis("professeurs", ecriture=True)
def professeur_supprimer(request, pk):
    professeur = get_object_or_404(filtrer(request.user, "professeurs", Professeur.objects.all(), ecriture=True), pk=pk)
    if request.method == "POST":
        professeur.delete()
        messages.success(request, "Professeur supprimé(e)!")
        return redirect("core:professeur_liste")
    return render(request, "core/confirm_delete.html", {"objet": professeur, "retour": "core:professeur_liste"})


# ─────────────────────────── EMPLOYÉS ───────────────────────────
@acces_requis("employes")
def employe_liste(request):
    employes = filtrer(request.user, "employes", Employe.objects.select_related("section"))
    return render(request, "core/employe_liste.html", {"employes": employes})


@acces_requis("employes", ecriture=True)
def employe_creer(request):
    if request.method == "POST":
        form = EmployeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Employé(e) ajouté(e) avec succès!")
            return redirect("core:employe_liste")
    else:
        form = EmployeForm()
    return render(request, "core/generic_form.html", {"form": form, "icone_titre": "ajouter", "titre": "Nouvel Employé"})


@acces_requis("employes", ecriture=True)
def employe_modifier(request, pk):
    employe = get_object_or_404(filtrer(request.user, "employes", Employe.objects.all(), ecriture=True), pk=pk)
    if request.method == "POST":
        form = EmployeForm(request.POST, instance=employe)
        if form.is_valid():
            form.save()
            messages.success(request, "Employé(e) modifié(e) avec succès!")
            return redirect("core:employe_liste")
    else:
        form = EmployeForm(instance=employe)
    return render(request, "core/generic_form.html", {"form": form, "titre": "Modifier l'Employé"})


@acces_requis("employes", ecriture=True)
def employe_supprimer(request, pk):
    employe = get_object_or_404(filtrer(request.user, "employes", Employe.objects.all(), ecriture=True), pk=pk)
    if request.method == "POST":
        employe.delete()
        messages.success(request, "Employé(e) supprimé(e)!")
        return redirect("core:employe_liste")
    return render(request, "core/confirm_delete.html", {"objet": employe, "retour": "core:employe_liste"})


# ─────────────────────────── PAIEMENTS ───────────────────────────
@acces_requis("paiements")
def paiement_liste(request):
    paiements = filtrer(request.user, "paiements", Paiement.objects.select_related("eleve"))
    total = paiements.filter(statut="Payé").aggregate(total=Sum("montant"))["total"] or 0
    return render(request, "core/paiement_liste.html", {"paiements": paiements, "total": total})


@acces_requis("paiements", ecriture=True)
def paiement_creer(request):
    if request.method == "POST":
        form = PaiementForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Paiement enregistré avec succès!")
            return redirect("core:paiement_liste")
    else:
        form = PaiementForm(initial={"statut": "Payé"})
    return render(request, "core/generic_form.html", {"form": form, "icone_titre": "ajouter", "titre": "Nouveau Paiement"})


@acces_requis("paiements", ecriture=True)
def paiement_supprimer(request, pk):
    paiement = get_object_or_404(filtrer(request.user, "paiements", Paiement.objects.all(), ecriture=True), pk=pk)
    if request.method == "POST":
        paiement.delete()
        messages.success(request, "Paiement supprimé!")
        return redirect("core:paiement_liste")
    return render(request, "core/confirm_delete.html", {"objet": paiement, "retour": "core:paiement_liste"})


# ─────────────────────────── NOTES ───────────────────────────
@acces_requis("notes")
def note_liste(request):
    q = request.GET.get("q", "").strip()
    notes = filtrer(request.user, "notes", Note.objects.select_related("eleve", "eleve__classe", "professeur"))
    if q:
        notes = notes.filter(Q(eleve__nom__icontains=q) | Q(eleve__prenom__icontains=q) | Q(matiere__icontains=q)
                             | Q(professeur__nom__icontains=q))
    # Filtres pour retrouver les notes d'une classe ou d'un trimestre
    classes = filtrer(request.user, "classes", Classe.objects.all()) if peut(request.user, "classes") else Classe.objects.none()
    classe = request.GET.get("classe", "")
    if classe.isdigit():
        notes = notes.filter(eleve__classe_id=classe)
    periode = request.GET.get("periode", "")
    if periode in choices.PERIODES:
        notes = notes.filter(periode=periode)
    return render(request, "core/note_liste.html", {
        "notes": notes, "q": q, "classes": classes, "classe": classe,
        "periodes": choices.PERIODES, "periode": periode,
    })


@acces_requis("notes", ecriture=True)
def note_modifier(request, pk):
    note = get_object_or_404(filtrer(request.user, "notes", Note.objects.all(), ecriture=True), pk=pk)
    if request.method == "POST":
        form = NoteForm(request.POST, instance=note, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Note corrigée.")
            return redirect("core:note_liste")
    else:
        form = NoteForm(instance=note, user=request.user)
    return render(request, "core/generic_form.html", {"form": form, "titre": "Corriger une note"})


@acces_requis("notes", ecriture=True)
def note_supprimer(request, pk):
    note = get_object_or_404(filtrer(request.user, "notes", Note.objects.all(), ecriture=True), pk=pk)
    if request.method == "POST":
        note.delete()
        messages.success(request, "Note supprimée!")
        return redirect("core:note_liste")
    return render(request, "core/confirm_delete.html", {"objet": note, "retour": "core:note_liste"})
