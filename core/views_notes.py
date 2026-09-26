# core/views_notes.py
# Saisie des notes par le professeur connecté : une grille avec les élèves
# d'une classe, pour une matière et un trimestre. L'administration ne saisit
# pas de notes (voir LECTURE_SEULE_POUR_TOUT_VOIR dans core/roles.py).
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.text import slugify

from . import choices, professeurs
from . import notes as outils_notes
from .models import Note
from .roles import professeur_de
from .templatetags.notes import note as format_note


def _lire_note(texte):
    """« 85 », « 72,5 » ou vide. Renvoie (valeur ou None, message d'erreur ou None)."""
    texte = (texte or "").strip().replace(",", ".")
    if not texte:
        return None, None
    try:
        valeur = Decimal(texte)
    except InvalidOperation:
        return None, "Écrivez un nombre, par exemple 75 ou 72,5."
    if not valeur.is_finite() or not (0 <= valeur <= 100):
        return None, "La note doit être comprise entre 0 et 100."
    if valeur != valeur.quantize(Decimal("0.01")):
        return None, "Deux chiffres après la virgule au plus."
    return valeur, None


def ancre(classe, matiere):
    """Repère d'une matière d'une classe dans la page « Mes notes »."""
    return f"g-{classe.pk if classe else 0}-{slugify(matiere)}"


def _lien_saisie(classe, matiere, periode):
    return f"{reverse('core:saisie_notes')}?{urlencode({'choix': f'{classe.pk}:{matiere}', 'periode': periode})}"


@login_required
def saisie_notes(request):
    professeur = professeur_de(request.user)
    if professeur is None:
        raise PermissionDenied
    possibles = professeurs.matieres_a_noter(professeur)
    choix = [(f"{classe.pk}:{matiere}", f"{classe} · {matiere}") for classe, matieres in possibles.items() for matiere in matieres]

    donnees = request.POST if request.method == "POST" else request.GET
    choisi = donnees.get("choix") or (choix[0][0] if len(choix) == 1 else "")
    periode = donnees.get("periode") if donnees.get("periode") in choices.PERIODES else choices.PERIODES[0]
    annee = choices.annee_scolaire_courante()

    classe = matiere = None
    if choisi:
        # Seulement une classe et une matière de ce professeur
        classe = next((c for c in possibles if choisi.startswith(f"{c.pk}:")), None)
        matiere = choisi.split(":", 1)[1] if classe else None
        if classe is None or matiere not in possibles[classe]:
            raise PermissionDenied

    lignes, erreurs = [], 0
    if classe is not None:
        eleves = list(classe.eleves.order_by("nom", "prenom"))
        existantes = {}
        for note in Note.objects.filter(eleve__in=eleves, matiere=matiere, periode=periode, annee_scolaire=annee) \
                .order_by("date_note"):
            existantes[note.eleve_id] = note  # la plus récente gagne
        for eleve in eleves:
            note = existantes.get(eleve.pk)
            ligne = {"eleve": eleve, "note": note, "valeur": "", "erreur": None}
            if request.method == "POST":
                ligne["valeur"] = request.POST.get(f"note_{eleve.pk}", "").strip()
                ligne["nouvelle"], ligne["erreur"] = _lire_note(ligne["valeur"])
                erreurs += ligne["erreur"] is not None
            elif note is not None:
                ligne["valeur"] = format_note(note.note)
            lignes.append(ligne)

        if request.method == "POST" and not erreurs:
            nb = 0
            with transaction.atomic():
                for ligne in lignes:
                    note, nouvelle = ligne["note"], ligne["nouvelle"]
                    if nouvelle is None:
                        if note is not None:  # champ vidé : la note est retirée
                            note.delete()
                            nb += 1
                    elif note is None:
                        Note.objects.create(eleve=ligne["eleve"], professeur=professeur, matiere=matiere,
                                            note=nouvelle, periode=periode, annee_scolaire=annee)
                        nb += 1
                    elif note.note != nouvelle:
                        note.note, note.professeur = nouvelle, professeur
                        note.save(update_fields=["note", "professeur"])
                        nb += 1
            messages.success(request, f"Notes enregistrées ({nb} changement{'s' if nb > 1 else ''}). Les voici dans « Mes notes ».")
            # Le professeur retrouve tout de suite ses notes dans son espace « Mes notes »
            return redirect(f"{reverse('core:mes_notes')}#{ancre(classe, matiere)}")
        if erreurs:
            messages.error(request, "Rien n'a été enregistré : corrigez les notes en rouge.")

    return render(request, "core/saisie_notes.html", {
        "choix": choix, "choisi": choisi, "periodes": choices.PERIODES, "periode": periode, "annee": annee,
        "classe": classe, "matiere": matiere, "lignes": lignes,
        "nb_notes": sum(1 for ligne in lignes if ligne["note"] is not None),
    })


@login_required
def mes_notes(request):
    """Les notes saisies par le professeur cette année, par classe puis par matière."""
    professeur = professeur_de(request.user)
    if professeur is None:
        raise PermissionDenied
    annee = choices.annee_scolaire_courante()
    possibles = professeurs.matieres_a_noter(professeur)
    notes = list(Note.objects.filter(professeur=professeur, annee_scolaire=annee)
                 .select_related("eleve", "eleve__classe", "eleve__classe__section", "professeur"))
    classes_notes = outils_notes.grouper(notes, toute_la_classe=True)
    for groupe in classes_notes:
        classe = groupe["classe"]
        for m in groupe["matieres"]:
            m["ancre"] = ancre(classe, m["matiere"])
            # Un crayon par trimestre pour rouvrir la grille, tant que la matière est encore la sienne
            peut_saisir = classe is not None and m["matiere"] in possibles.get(classe, [])
            m["saisie"] = [_lien_saisie(classe, m["matiere"], p) if peut_saisir else "" for p in choices.PERIODES]
    return render(request, "core/mes_notes.html", {
        "annee": annee, "classes_notes": classes_notes, "periodes": choices.PERIODES,
        "nb_notes": len(notes), "a_noter": bool(possibles),
    })
