# core/views_fiches.py
# Fiches d'une personne ou d'une classe (élève, employé, classe) et photos.
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from . import choices
from . import notes as outils_notes
from .models import Classe, Cours, Eleve, Employe, Note, Preinscription, Professeur
from .roles import acces_requis, filtrer, parent_de, peut, professeur_de


# ─────────────────────────── Photos ───────────────────────────
def _photo_visible(user, objet):
    """Qui peut voir une photo : ceux qui voient la fiche, la personne elle-même,
    le parent pour ses enfants et le professeur pour les élèves de ses classes."""
    if isinstance(objet, Preinscription):
        return filtrer(user, "preinscriptions", Preinscription.objects.filter(pk=objet.pk)).exists()
    if isinstance(objet, Eleve):
        if filtrer(user, "eleves", Eleve.objects.filter(pk=objet.pk)).exists():
            return True
        parent = parent_de(user)
        if parent is not None and parent.enfants.filter(pk=objet.pk).exists():
            return True
        professeur = professeur_de(user)
        return professeur is not None and objet.classe_id is not None \
            and professeur.classes.filter(pk=objet.classe_id).exists()
    module = "professeurs" if isinstance(objet, Professeur) else "employes"
    if objet.utilisateur_id == user.pk:
        return True
    return filtrer(user, module, type(objet).objects.filter(pk=objet.pk)).exists()


MODELES_AVEC_PHOTO = {"eleve": Eleve, "professeur": Professeur, "employe": Employe, "preinscription": Preinscription}


@login_required
def photo(request, modele, pk):
    classe_modele = MODELES_AVEC_PHOTO.get(modele)
    if classe_modele is None:
        raise Http404
    objet = get_object_or_404(classe_modele, pk=pk)
    # 404 et non 403 : on ne dit pas si la personne existe
    if not objet.photo or not _photo_visible(request.user, objet):
        raise Http404
    try:
        fichier = objet.photo.open("rb")
    except FileNotFoundError:
        raise Http404
    reponse = FileResponse(fichier, content_type="image/jpeg")
    reponse["Cache-Control"] = "private, max-age=3600"
    return reponse


# ─────────────────────────── Élève ───────────────────────────
@acces_requis("eleves")
def eleve_fiche(request, pk):
    eleve = get_object_or_404(filtrer(request.user, "eleves", Eleve.objects.select_related("classe", "classe__section")), pk=pk)
    contexte = {"eleve": eleve, "periodes": choices.PERIODES}
    if peut(request.user, "parents"):
        contexte["familles"] = eleve.parents.select_related("utilisateur")
    if peut(request.user, "notes"):
        notes = filtrer(request.user, "notes", Note.objects.filter(eleve=eleve).select_related("eleve", "eleve__classe", "professeur"))
        contexte["classes_notes"] = outils_notes.grouper(notes)
    return render(request, "core/eleve_fiche.html", contexte)


# ─────────────────────────── Classe ───────────────────────────
@acces_requis("classes")
def classe_fiche(request, pk):
    classe = get_object_or_404(filtrer(request.user, "classes", Classe.objects.select_related("section")), pk=pk)
    eleves = list(classe.eleves.order_by("nom", "prenom"))
    affectations = classe.affectations.filter(date_fin__isnull=True).select_related("professeur")
    # Au secondaire : les professeurs qui ont cours dans la classe cette année, avec leurs matières
    professeurs_cours = {}
    for cours in Cours.objects.filter(classe=classe, annee_scolaire=choices.annee_scolaire_courante()) \
            .select_related("professeur").order_by("professeur__nom", "matiere"):
        professeur = professeurs_cours.setdefault(cours.professeur_id, cours.professeur)
        professeur.matieres_ici = getattr(professeur, "matieres_ici", [])
        if cours.matiere not in professeur.matieres_ici:
            professeur.matieres_ici.append(cours.matiere)
    nb_filles = sum(1 for e in eleves if e.genre == "Féminin")
    return render(request, "core/classe_fiche.html", {
        "classe": classe,
        "eleves": eleves if peut(request.user, "eleves") else None,
        "nb_eleves": len(eleves), "nb_filles": nb_filles, "nb_garcons": len(eleves) - nb_filles,
        "affectations": affectations,
        "professeurs_cours": list(professeurs_cours.values()),
    })


# ─────────────────────────── Employé ───────────────────────────
@acces_requis("employes")
def employe_fiche(request, pk):
    employe = get_object_or_404(filtrer(request.user, "employes", Employe.objects.select_related("section", "utilisateur")), pk=pk)
    return render(request, "core/employe_fiche.html", {"employe": employe})
