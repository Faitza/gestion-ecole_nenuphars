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
from . import choices


class LoginView(auth_views.LoginView):
    template_name = "core/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


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
    return render(request, "core/generic_form.html", {"form": form, "titre": "➕ Nouvel Élève"})


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
    return render(request, "core/generic_form.html", {"form": form, "titre": "✏️ Modifier l'Élève"})


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
    return render(request, "core/generic_form.html", {"form": form, "titre": "➕ Nouvelle Classe"})


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
    return render(request, "core/generic_form.html", {"form": form, "titre": "✏️ Modifier la Classe"})


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
    professeurs = filtrer(request.user, "professeurs", Professeur.objects.select_related("section").prefetch_related("classes"))
    return render(request, "core/professeur_liste.html", {"professeurs": professeurs})


@acces_requis("professeurs", ecriture=True)
def professeur_creer(request):
    if request.method == "POST":
        form = ProfesseurForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Professeur ajouté(e) avec succès!")
            return redirect("core:professeur_liste")
    else:
        form = ProfesseurForm()
    return render(request, "core/generic_form.html", {"form": form, "titre": "➕ Nouveau Professeur"})


@acces_requis("professeurs", ecriture=True)
def professeur_modifier(request, pk):
    professeur = get_object_or_404(filtrer(request.user, "professeurs", Professeur.objects.all(), ecriture=True), pk=pk)
    if request.method == "POST":
        form = ProfesseurForm(request.POST, instance=professeur)
        if form.is_valid():
            form.save()
            messages.success(request, "Professeur modifié(e) avec succès!")
            return redirect("core:professeur_liste")
    else:
        form = ProfesseurForm(instance=professeur, initial={"classes": professeur.classes.all()})
    return render(request, "core/generic_form.html", {"form": form, "titre": "✏️ Modifier le Professeur"})


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
    return render(request, "core/generic_form.html", {"form": form, "titre": "➕ Nouvel Employé"})


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
    return render(request, "core/generic_form.html", {"form": form, "titre": "✏️ Modifier l'Employé"})


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
    return render(request, "core/generic_form.html", {"form": form, "titre": "➕ Nouveau Paiement"})


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
    notes = filtrer(request.user, "notes", Note.objects.select_related("eleve", "professeur"))
    if q:
        notes = notes.filter(Q(eleve__nom__icontains=q) | Q(matiere__icontains=q))
    return render(request, "core/note_liste.html", {"notes": notes, "q": q})


@acces_requis("notes", ecriture=True)
def note_creer(request):
    if request.method == "POST":
        form = NoteForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Note ajoutée avec succès!")
            return redirect("core:note_liste")
    else:
        form = NoteForm(user=request.user)
    return render(request, "core/generic_form.html", {"form": form, "titre": "➕ Ajouter une Note"})


@acces_requis("notes", ecriture=True)
def note_modifier(request, pk):
    note = get_object_or_404(filtrer(request.user, "notes", Note.objects.all(), ecriture=True), pk=pk)
    if request.method == "POST":
        form = NoteForm(request.POST, instance=note, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Note modifiée avec succès!")
            return redirect("core:note_liste")
    else:
        form = NoteForm(instance=note, user=request.user)
    return render(request, "core/generic_form.html", {"form": form, "titre": "✏️ Modifier la Note"})


@acces_requis("notes", ecriture=True)
def note_supprimer(request, pk):
    note = get_object_or_404(filtrer(request.user, "notes", Note.objects.all(), ecriture=True), pk=pk)
    if request.method == "POST":
        note.delete()
        messages.success(request, "Note supprimée!")
        return redirect("core:note_liste")
    return render(request, "core/confirm_delete.html", {"objet": note, "retour": "core:note_liste"})
