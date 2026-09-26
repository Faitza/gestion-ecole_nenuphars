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

from . import choices, professeurs
from .models import Note
from .roles import professeur_de


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
                ligne["valeur"] = f"{note.note.normalize():f}".replace(".", ",")
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
            messages.success(request, f"Notes enregistrées ({nb} changement{'s' if nb > 1 else ''}).")
            return redirect(f"{reverse('core:saisie_notes')}?{urlencode({'choix': choisi, 'periode': periode})}")
        if erreurs:
            messages.error(request, "Rien n'a été enregistré : corrigez les notes en rouge.")

    return render(request, "core/saisie_notes.html", {
        "choix": choix, "choisi": choisi, "periodes": choices.PERIODES, "periode": periode, "annee": annee,
        "classe": classe, "matiere": matiere, "lignes": lignes,
        "nb_notes": sum(1 for ligne in lignes if ligne["note"] is not None),
    })
