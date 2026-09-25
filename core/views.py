# core/views.py
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Q

from .models import Eleve, Professeur, Employe, Paiement, Note, Classe
from .forms import LoginForm, EleveForm, ProfesseurForm, EmployeForm, PaiementForm, NoteForm, ClasseForm
from . import choices


class LoginView(auth_views.LoginView):
    template_name = "core/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    next_page = "core:login"


@login_required
def dashboard(request):
    context = {
        "nb_eleves": Eleve.objects.count(),
        "nb_professeurs": Professeur.objects.count(),
        "nb_employes": Employe.objects.count(),
        "revenus": Paiement.objects.filter(statut="Payé").aggregate(total=Sum("montant"))["total"] or 0,
    }
    return render(request, "core/dashboard.html", context)


# ─────────────────────────── ÉLÈVES ───────────────────────────
@login_required
def eleve_liste(request):
    q = request.GET.get("q", "").strip()
    eleves = Eleve.objects.select_related("classe")
    if q:
        eleves = eleves.filter(Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(nom_parent_tuteur__icontains=q))
    return render(request, "core/eleve_liste.html", {"eleves": eleves, "q": q})


@login_required
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


@login_required
def eleve_modifier(request, pk):
    eleve = get_object_or_404(Eleve, pk=pk)
    if request.method == "POST":
        form = EleveForm(request.POST, instance=eleve)
        if form.is_valid():
            form.save()
            messages.success(request, "Élève modifié(e) avec succès!")
            return redirect("core:eleve_liste")
    else:
        form = EleveForm(instance=eleve)
    return render(request, "core/generic_form.html", {"form": form, "titre": "✏️ Modifier l'Élève"})


@login_required
def eleve_supprimer(request, pk):
    eleve = get_object_or_404(Eleve, pk=pk)
    if request.method == "POST":
        eleve.delete()
        messages.success(request, "Élève supprimé(e)!")
        return redirect("core:eleve_liste")
    return render(request, "core/confirm_delete.html", {"objet": eleve, "retour": "core:eleve_liste"})


# ─────────────────────────── CLASSES ───────────────────────────
@login_required
def classe_liste(request):
    return render(request, "core/classe_liste.html", {"classes": Classe.objects.all()})


@login_required
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


@login_required
def classe_modifier(request, pk):
    classe = get_object_or_404(Classe, pk=pk)
    if request.method == "POST":
        form = ClasseForm(request.POST, instance=classe)
        if form.is_valid():
            form.save()
            messages.success(request, "Classe modifiée avec succès!")
            return redirect("core:classe_liste")
    else:
        form = ClasseForm(instance=classe)
    return render(request, "core/generic_form.html", {"form": form, "titre": "✏️ Modifier la Classe"})


@login_required
def classe_supprimer(request, pk):
    classe = get_object_or_404(Classe, pk=pk)
    if request.method == "POST":
        classe.delete()
        messages.success(request, "Classe supprimée!")
        return redirect("core:classe_liste")
    return render(request, "core/confirm_delete.html", {"objet": classe, "retour": "core:classe_liste"})


# ─────────────────────────── PROFESSEURS ───────────────────────────
@login_required
def professeur_liste(request):
    return render(request, "core/professeur_liste.html", {"professeurs": Professeur.objects.prefetch_related("classes")})


@login_required
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


@login_required
def professeur_modifier(request, pk):
    professeur = get_object_or_404(Professeur, pk=pk)
    if request.method == "POST":
        form = ProfesseurForm(request.POST, instance=professeur)
        if form.is_valid():
            form.save()
            messages.success(request, "Professeur modifié(e) avec succès!")
            return redirect("core:professeur_liste")
    else:
        form = ProfesseurForm(instance=professeur, initial={"classes": professeur.classes.all()})
    return render(request, "core/generic_form.html", {"form": form, "titre": "✏️ Modifier le Professeur"})


@login_required
def professeur_supprimer(request, pk):
    professeur = get_object_or_404(Professeur, pk=pk)
    if request.method == "POST":
        professeur.delete()
        messages.success(request, "Professeur supprimé(e)!")
        return redirect("core:professeur_liste")
    return render(request, "core/confirm_delete.html", {"objet": professeur, "retour": "core:professeur_liste"})


# ─────────────────────────── EMPLOYÉS ───────────────────────────
@login_required
def employe_liste(request):
    return render(request, "core/employe_liste.html", {"employes": Employe.objects.all()})


@login_required
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


@login_required
def employe_modifier(request, pk):
    employe = get_object_or_404(Employe, pk=pk)
    if request.method == "POST":
        form = EmployeForm(request.POST, instance=employe)
        if form.is_valid():
            form.save()
            messages.success(request, "Employé(e) modifié(e) avec succès!")
            return redirect("core:employe_liste")
    else:
        form = EmployeForm(instance=employe)
    return render(request, "core/generic_form.html", {"form": form, "titre": "✏️ Modifier l'Employé"})


@login_required
def employe_supprimer(request, pk):
    employe = get_object_or_404(Employe, pk=pk)
    if request.method == "POST":
        employe.delete()
        messages.success(request, "Employé(e) supprimé(e)!")
        return redirect("core:employe_liste")
    return render(request, "core/confirm_delete.html", {"objet": employe, "retour": "core:employe_liste"})


# ─────────────────────────── PAIEMENTS ───────────────────────────
@login_required
def paiement_liste(request):
    paiements = Paiement.objects.select_related("eleve")
    total = paiements.filter(statut="Payé").aggregate(total=Sum("montant"))["total"] or 0
    return render(request, "core/paiement_liste.html", {"paiements": paiements, "total": total})


@login_required
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


@login_required
def paiement_supprimer(request, pk):
    paiement = get_object_or_404(Paiement, pk=pk)
    if request.method == "POST":
        paiement.delete()
        messages.success(request, "Paiement supprimé!")
        return redirect("core:paiement_liste")
    return render(request, "core/confirm_delete.html", {"objet": paiement, "retour": "core:paiement_liste"})


# ─────────────────────────── NOTES ───────────────────────────
@login_required
def note_liste(request):
    q = request.GET.get("q", "").strip()
    notes = Note.objects.select_related("eleve", "professeur")
    if q:
        notes = notes.filter(Q(eleve__nom__icontains=q) | Q(matiere__icontains=q))
    return render(request, "core/note_liste.html", {"notes": notes, "q": q})


@login_required
def note_creer(request):
    if request.method == "POST":
        form = NoteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Note ajoutée avec succès!")
            return redirect("core:note_liste")
    else:
        form = NoteForm()
    return render(request, "core/generic_form.html", {"form": form, "titre": "➕ Ajouter une Note"})


@login_required
def note_modifier(request, pk):
    note = get_object_or_404(Note, pk=pk)
    if request.method == "POST":
        form = NoteForm(request.POST, instance=note)
        if form.is_valid():
            form.save()
            messages.success(request, "Note modifiée avec succès!")
            return redirect("core:note_liste")
    else:
        form = NoteForm(instance=note)
    return render(request, "core/generic_form.html", {"form": form, "titre": "✏️ Modifier la Note"})


@login_required
def note_supprimer(request, pk):
    note = get_object_or_404(Note, pk=pk)
    if request.method == "POST":
        note.delete()
        messages.success(request, "Note supprimée!")
        return redirect("core:note_liste")
    return render(request, "core/confirm_delete.html", {"objet": note, "retour": "core:note_liste"})
