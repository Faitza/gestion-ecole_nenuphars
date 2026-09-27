# core/views_bulletins.py
# Bulletins trimestriels : la direction de la section suit l'avancement de la
# saisie des notes, le censeur donne la conduite, la direction écrit son
# appréciation puis valide les bulletins d'une classe. Les parents les voient
# ensuite dans leur espace, et on peut tous les imprimer (ou les enregistrer
# en PDF depuis le navigateur) en un clic.
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import bulletins as calcul
from . import bulletins_fichiers, choices
from .classes import dans_l_ordre
from .models import Bulletin, Classe
from .roles import acces_requis, filtrer, peut_donner_la_conduite, peut_valider_bulletins


def _periode(request):
    periode = request.POST.get("periode") or request.GET.get("periode")
    return periode if periode in choices.PERIODES else choices.trimestre_du_jour()


def _classes(user):
    return filtrer(user, "bulletins", Classe.objects.select_related("section"), chemin="section")


@acces_requis("bulletins")
def bulletins_liste(request):
    periode, annee = _periode(request), choices.annee_scolaire_courante()
    classes = dans_l_ordre(_classes(request.user))
    for classe in classes:
        classe.avancement = calcul.avancement(classe, periode, annee)
        classe.peut_valider = peut_valider_bulletins(request.user, classe.section)
    return render(request, "core/bulletins_liste.html", {
        "classes": classes, "periode": periode, "periodes": choices.PERIODES, "annee": annee,
        "a_valider": sum(1 for c in classes if c.peut_valider and c.avancement["etat"] == calcul.ETAT_A_VALIDER),
    })


def _remarques(request, eleves, conduite, appreciation):
    remarques = {}
    for eleve in eleves:
        champs = {}
        if conduite:
            valeur = request.POST.get(f"c{eleve.pk}", "")
            if valeur in choices.CONDUITES or valeur == "":
                champs["conduite"] = valeur
        if appreciation:
            champs["appreciation"] = request.POST.get(f"a{eleve.pk}", "").strip()[:500]
        remarques[eleve.pk] = champs
    return remarques


@acces_requis("bulletins")
def bulletins_classe(request, pk):
    classe = get_object_or_404(_classes(request.user), pk=pk)
    periode, annee = _periode(request), choices.annee_scolaire_courante()
    conduite = peut_donner_la_conduite(request.user, classe.section)
    valider = peut_valider_bulletins(request.user, classe.section)
    eleves = list(classe.eleves.order_by("nom", "prenom"))
    publies = Bulletin.objects.filter(classe=classe, periode=periode, annee_scolaire=annee, valide=True).exists()

    if request.method == "POST":
        action = request.POST.get("action")
        if action not in ("enregistrer", "valider", "retirer") or (action != "enregistrer" and not valider) \
                or not (conduite or valider):
            raise PermissionDenied
        if publies and action != "retirer":
            # Un bulletin publié ne change pas sous les yeux des parents : on retire, on corrige, on revalide.
            messages.error(request, "Ces bulletins sont publiés. Retirez d'abord la publication pour les corriger.")
            return redirect(f"{reverse('core:bulletins_classe', args=[classe.pk])}?periode={periode}")
        if action in ("enregistrer", "valider"):
            calcul.enregistrer_remarques(classe, periode, annee, _remarques(request, eleves, conduite, valider))
        if action == "valider":
            calcul.valider(classe, periode, annee, request.user)
            messages.success(request, f"Bulletins du {periode} de {classe} validés : les parents les voient maintenant.")
        elif action == "retirer":
            calcul.retirer(classe, periode, annee)
            messages.success(request, "Les parents ne voient plus ces bulletins. Corrigez puis validez de nouveau.")
        else:
            messages.success(request, "Conduite et appréciations enregistrées.")
        return redirect(f"{reverse('core:bulletins_classe', args=[classe.pk])}?periode={periode}")

    resultats = calcul.calculer(classe, periode, annee)
    brouillons = calcul.brouillons(classe, periode, annee)
    lignes = []
    for eleve in eleves:
        bulletin = brouillons.get(eleve.pk)
        valeurs = calcul.apercu(bulletin if bulletin and bulletin.valide else resultats[eleve.pk])
        lignes.append({"eleve": eleve, "bulletin": bulletin, **valeurs})
    lignes.sort(key=lambda l: (l["rang"] is None, l["rang"] or 0, l["eleve"].nom))
    avancement = calcul.avancement(classe, periode, annee)
    valide = next((b for b in brouillons.values() if b.valide), None)
    return render(request, "core/bulletins_classe.html", {
        "classe": classe, "periode": periode, "periodes": choices.PERIODES, "annee": annee,
        "lignes": lignes, "avancement": avancement, "valide": valide,
        "conduite": conduite and not publies, "valider": valider, "publies": publies, "conduites": choices.CONDUITES,
    })


def _bulletin_de(classe, eleve, periode, annee):
    """Le bulletin validé, ou l'aperçu calculé maintenant."""
    bulletin = Bulletin.objects.filter(eleve=eleve, periode=periode, annee_scolaire=annee).select_related("valide_par").first()
    if bulletin is not None and bulletin.valide:
        return bulletin, calcul.apercu(bulletin)
    return bulletin, calcul.apercu(calcul.calculer(classe, periode, annee)[eleve.pk])


def telechargement(contenu, nom, extension):
    """Réponse qui fait télécharger le fichier (PDF ou PNG) sous un nom lisible."""
    reponse = HttpResponse(contenu, content_type="application/pdf" if extension == "pdf" else "image/png")
    reponse["Content-Disposition"] = f'attachment; filename="{nom}"'
    return reponse


def fichier_du_bulletin(fiche, periode, annee, format):
    """Le bulletin d'un élève en PDF ou en PNG, prêt à télécharger."""
    if format not in ("pdf", "png"):
        raise Http404
    contenu = (bulletins_fichiers.pdf([fiche], periode, annee) if format == "pdf"
               else bulletins_fichiers.png(fiche, periode, annee))
    return telechargement(contenu, bulletins_fichiers.nom_de_fichier(periode, annee, format, eleve=fiche["eleve"]), format)


def _fiche_eleve(request, pk, eleve_pk):
    classe = get_object_or_404(_classes(request.user), pk=pk)
    eleve = get_object_or_404(classe.eleves, pk=eleve_pk)
    periode, annee = _periode(request), choices.annee_scolaire_courante()
    bulletin, valeurs = _bulletin_de(classe, eleve, periode, annee)
    return {"eleve": eleve, "classe": classe, "bulletin": bulletin, **valeurs}, periode, annee


@acces_requis("bulletins")
def bulletin_eleve(request, pk, eleve_pk):
    fiche, periode, annee = _fiche_eleve(request, pk, eleve_pk)
    suffixe = f"?periode={periode}"
    return render(request, "core/bulletin.html", {
        "fiches": [fiche], "periode": periode, "annee": annee,
        "retour": f"{reverse('core:bulletins_classe', args=[pk])}{suffixe}",
        "lien_pdf": f"{reverse('core:bulletin_eleve_fichier', args=[pk, eleve_pk, 'pdf'])}{suffixe}",
        "lien_png": f"{reverse('core:bulletin_eleve_fichier', args=[pk, eleve_pk, 'png'])}{suffixe}",
    })


@acces_requis("bulletins")
def bulletin_eleve_fichier(request, pk, eleve_pk, format):
    fiche, periode, annee = _fiche_eleve(request, pk, eleve_pk)
    return fichier_du_bulletin(fiche, periode, annee, format)


def _fiches_de_la_classe(request, pk):
    classe = get_object_or_404(_classes(request.user), pk=pk)
    periode, annee = _periode(request), choices.annee_scolaire_courante()
    resultats = calcul.calculer(classe, periode, annee)
    brouillons = calcul.brouillons(classe, periode, annee)
    fiches = []
    for eleve in classe.eleves.order_by("nom", "prenom"):
        bulletin = brouillons.get(eleve.pk)
        valeurs = calcul.apercu(bulletin if bulletin and bulletin.valide else resultats[eleve.pk])
        fiches.append({"eleve": eleve, "classe": classe, "bulletin": bulletin, **valeurs})
    if not fiches:
        raise Http404
    return classe, fiches, periode, annee


@acces_requis("bulletins")
def bulletins_imprimer(request, pk):
    classe, fiches, periode, annee = _fiches_de_la_classe(request, pk)
    return render(request, "core/bulletin.html", {
        "fiches": fiches, "periode": periode, "annee": annee, "toute_la_classe": True,
        "retour": f"{reverse('core:bulletins_classe', args=[classe.pk])}?periode={periode}",
        "lien_pdf": f"{reverse('core:bulletins_classe_pdf', args=[classe.pk])}?periode={periode}",
    })


@acces_requis("bulletins")
def bulletins_classe_pdf(request, pk):
    """Tous les bulletins de la classe dans un seul PDF, une page par élève."""
    classe, fiches, periode, annee = _fiches_de_la_classe(request, pk)
    return telechargement(bulletins_fichiers.pdf(fiches, periode, annee),
                          bulletins_fichiers.nom_de_fichier(periode, annee, "pdf", classe=classe), "pdf")
