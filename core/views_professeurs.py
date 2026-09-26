# core/views_professeurs.py
# Inscription des professeurs par la secrétaire, fiche, emploi du temps.
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import anniversaires, choices, professeurs
from .forms import AffectationForm, CoursFormSet, ProfesseurForm
from .models import Affectation, Cours, Creneau, Professeur, Section
from .roles import acces_requis, filtrer, peut, peut_valider_cours

_CLE_MOT_DE_PASSE = "mot_de_passe_provisoire_{}"


def _professeur(request, pk, ecriture=False):
    return get_object_or_404(filtrer(request.user, "professeurs", Professeur.objects.select_related("section", "utilisateur"),
                                     ecriture=ecriture), pk=pk)


def _section_choisie(request):
    valeur = request.POST.get("section") or request.GET.get("section")
    return Section.objects.filter(pk=valeur).first() if valeur and str(valeur).isdigit() else None


# ─────────────────────────── Inscription ───────────────────────────
@acces_requis("professeurs", ecriture=True)
def professeur_inscrire(request):
    section = _section_choisie(request)
    if section is None:
        return render(request, "core/professeur_inscrire.html", {"sections": Section.objects.all()})

    donnees = request.POST if request.method == "POST" else None
    form = ProfesseurForm(donnees, section=section)
    affectation_form = None if section.est_secondaire else AffectationForm(donnees, section=section, prefix="aff")
    cours_formset = CoursFormSet(donnees, section=section, prefix="cours") if section.est_secondaire else None
    horaires_manquants = section.est_secondaire and not Creneau.objects.filter(section=section, est_un_cours=True).exists()

    if request.method == "POST":
        valide = form.is_valid() and (affectation_form.is_valid() if affectation_form else cours_formset.is_valid())
        if valide:
            try:
                with transaction.atomic():
                    professeur = form.save(commit=False)
                    professeur.section = section
                    professeur.save()
                    if affectation_form:
                        d = affectation_form.cleaned_data
                        professeurs.affecter(professeur, d["classe"], d["role"], remplacer=d["a_remplacer"])
                    else:
                        professeurs.ajouter_cours(professeur, cours_formset.lignes())
                    mot_de_passe = professeurs.creer_compte(professeur)
            except IntegrityError:
                messages.error(request, "Une classe ou un horaire vient d'être pris par une autre inscription. Vérifiez et recommencez.")
            else:
                request.session[_CLE_MOT_DE_PASSE.format(professeur.pk)] = mot_de_passe
                messages.success(request, f"{professeur.prenom} {professeur.nom} est inscrit(e) et son compte est créé.")
                return redirect("core:professeur_acces", pk=professeur.pk)

    return render(request, "core/professeur_inscrire.html", {
        "sections": Section.objects.all(), "section": section, "form": form,
        "affectation_form": affectation_form, "cours_formset": cours_formset,
        "horaires_manquants": horaires_manquants,
    })


@acces_requis("professeurs", ecriture=True)
def professeur_acces(request, pk):
    """Fiche d'accès à imprimer : identifiant et mot de passe provisoire (affiché une seule fois)."""
    professeur = _professeur(request, pk, ecriture=True)
    mot_de_passe = request.session.pop(_CLE_MOT_DE_PASSE.format(professeur.pk), None)
    return render(request, "core/professeur_acces.html", {"professeur": professeur, "mot_de_passe": mot_de_passe})


@require_POST
@acces_requis("professeurs", ecriture=True)
def professeur_nouveau_mot_de_passe(request, pk):
    professeur = _professeur(request, pk, ecriture=True)
    if professeur.utilisateur is None:
        if professeurs.telephone_deja_utilise(professeur.telephone):
            messages.error(request, "Ce numéro sert déjà d'identifiant à un autre compte : corrigez le téléphone.")
            return redirect("core:professeur_fiche", pk=pk)
        mot_de_passe = professeurs.creer_compte(professeur)
    else:
        mot_de_passe = professeurs.nouveau_mot_de_passe(professeur.utilisateur)
    request.session[_CLE_MOT_DE_PASSE.format(professeur.pk)] = mot_de_passe
    return redirect("core:professeur_acces", pk=pk)


# ─────────────────────────── Fiche ───────────────────────────
@acces_requis("professeurs")
def professeur_fiche(request, pk):
    professeur = _professeur(request, pk)
    section = professeur.section
    cours = list(professeurs.cours_de_l_annee(professeur))
    creneaux = Creneau.objects.filter(section=section) if section else Creneau.objects.none()
    a_valider = [c for c in cours if c.statut == choices.STATUT_COURS_PROPOSE]
    return render(request, "core/professeur_fiche.html", {
        "professeur": professeur,
        "affectation": professeur.affectation_active,
        "historique": professeur.affectations.filter(date_fin__isnull=False).select_related("classe")[:5],
        "cours": cours,
        "grille": professeurs.grille(cours, creneaux) if cours else [],
        "jours": [nom for _, nom in choices.JOURS_CHOICES],
        "resume": professeurs.resume(cours),
        "a_valider": a_valider,
        "peut_modifier": peut(request.user, "professeurs", ecriture=True),
        "peut_valider": bool(a_valider) and any(peut_valider_cours(request.user, c.classe.section) for c in a_valider),
        "annee": choices.annee_scolaire_courante(),
    })


@acces_requis("professeurs", ecriture=True)
def professeur_affecter(request, pk):
    """Kindergarten et primaire : changer la classe (ou le rôle) du professeur."""
    professeur = _professeur(request, pk, ecriture=True)
    if professeur.section is None or professeur.section.est_secondaire:
        raise Http404
    actuelle = professeur.affectation_active
    initial = {"classe": actuelle.classe_id, "role": actuelle.role} if actuelle else None
    form = AffectationForm(request.POST or None, initial=initial, section=professeur.section, professeur=professeur)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            professeurs.affecter(professeur, d["classe"], d["role"], remplacer=d["a_remplacer"])
        messages.success(request, f"{professeur} est maintenant en {d['classe']}.")
        return redirect("core:professeur_fiche", pk=pk)
    return render(request, "core/generic_form.html", {"form": form, "icone_titre": "classes", "titre": f"Classe de {professeur}"})


@require_POST
@acces_requis("professeurs", ecriture=True)
def affectation_terminer(request, pk):
    affectation = get_object_or_404(Affectation, pk=pk, date_fin__isnull=True)
    _professeur(request, affectation.professeur_id, ecriture=True)
    professeurs.terminer_affectation(affectation)
    messages.success(request, f"{affectation.professeur} n'est plus dans la classe {affectation.classe}.")
    return redirect("core:professeur_fiche", pk=affectation.professeur_id)


@acces_requis("professeurs", ecriture=True)
def professeur_cours(request, pk):
    """Secondaire : ajouter des cours à l'emploi du temps du professeur."""
    professeur = _professeur(request, pk, ecriture=True)
    if professeur.section is None or not professeur.section.est_secondaire:
        raise Http404
    formset = CoursFormSet(request.POST or None, section=professeur.section, professeur=professeur, prefix="cours")
    if request.method == "POST" and formset.is_valid():
        try:
            with transaction.atomic():
                professeurs.ajouter_cours(professeur, formset.lignes())
        except IntegrityError:
            messages.error(request, "Un de ces horaires vient d'être pris. Vérifiez et recommencez.")
        else:
            messages.success(request, "Cours ajoutés. Ils attendent la validation de la direction.")
            return redirect("core:professeur_fiche", pk=pk)
    return render(request, "core/professeur_cours.html", {"professeur": professeur, "cours_formset": formset})


@require_POST
@acces_requis("professeurs", ecriture=True)
def cours_supprimer(request, pk):
    cours = get_object_or_404(Cours.objects.select_related("professeur"), pk=pk)
    professeur = _professeur(request, cours.professeur_id, ecriture=True)
    cours.delete()
    professeurs.synchroniser_classes(professeur)
    messages.success(request, "Cours retiré.")
    return redirect("core:professeur_fiche", pk=professeur.pk)


@require_POST
@login_required
def professeur_valider_cours(request, pk):
    """La direction de la section valide les cours proposés ; l'emploi du temps devient visible du professeur."""
    professeur = get_object_or_404(Professeur, pk=pk)
    a_valider = professeurs.cours_de_l_annee(professeur).filter(statut=choices.STATUT_COURS_PROPOSE)
    valides = [c.pk for c in a_valider if peut_valider_cours(request.user, c.classe.section)]
    if not valides:
        raise PermissionDenied
    Cours.objects.filter(pk__in=valides).update(statut=choices.STATUT_COURS_VALIDE)
    messages.success(request, f"{len(valides)} cours validé(s).")
    return redirect("core:professeur_fiche", pk=pk)


# ─────────────────────────── Espace du professeur ───────────────────────────
def espace_professeur(request, professeur):
    """Ce que voit le professeur connecté : sa classe, ou son emploi du temps validé."""
    cours = [c for c in professeurs.cours_de_l_annee(professeur) if c.statut == choices.STATUT_COURS_VALIDE]
    creneaux = Creneau.objects.filter(section=professeur.section) if professeur.section else Creneau.objects.none()
    return render(request, "core/professeur_espace.html", {
        "professeur": professeur,
        "affectation": professeur.affectation_active,
        "grille": professeurs.grille(cours, creneaux) if cours else [],
        "jours": [nom for _, nom in choices.JOURS_CHOICES],
        "resume": professeurs.resume(cours),
        "en_attente": professeurs.cours_de_l_annee(professeur).filter(statut=choices.STATUT_COURS_PROPOSE).count(),
        "ma_fete": anniversaires.c_est_sa_fete(professeur),
        "a_noter": bool(professeurs.matieres_a_noter(professeur)),
    })
