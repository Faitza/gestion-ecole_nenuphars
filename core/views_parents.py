# core/views_parents.py
# Comptes parents (cahier des charges, section C). Le secrétariat remet à
# chaque famille une fiche avec un code d'accès à usage unique. Sur
# /inscription/, le parent entre ce code et son téléphone, choisit son mot de
# passe, puis voit seulement ses enfants sur /parents/ (notes de l'année et
# paiements).
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import choices, parents
from . import notes as outils_notes
from .forms import CodeParentForm, CompteExistantForm, MotDePasseParentForm
from .models import Eleve, Note, Parent
from .professeurs import nouveau_mot_de_passe
from .roles import acces_requis, filtrer, parent_de, peut

SESSION = "inscription_parent"
_CLE_MOT_DE_PASSE = "mot_de_passe_parent_{}"

# Au-delà de 10 essais ratés en 15 minutes depuis la même adresse, la page se
# bloque : on ne peut pas essayer des codes au hasard.
ESSAIS_MAX = 10
DUREE_BLOCAGE = 15 * 60


def _cle_essais(request):
    return f"inscription-parent:{request.META.get('REMOTE_ADDR', '')}"


def _trop_d_essais(request):
    return cache.get(_cle_essais(request), 0) >= ESSAIS_MAX


def _compter_un_echec(request):
    cle = _cle_essais(request)
    cache.add(cle, 0, DUREE_BLOCAGE)
    try:
        cache.incr(cle)
    except ValueError:  # la clé a expiré entre les deux lignes
        cache.set(cle, 1, DUREE_BLOCAGE)


def _prenoms(enfants):
    prenoms = [e.prenom for e in enfants]
    return prenoms[0] if len(prenoms) == 1 else ", ".join(prenoms[:-1]) + " et " + prenoms[-1]


# ─────────────────────────── Créer mon compte parent ───────────────────────────
def inscription(request):
    """Étape 1 : le code d'accès remis par l'école et le téléphone donné à l'inscription."""
    if request.user.is_authenticated:
        return redirect("core:espace")
    bloque = _trop_d_essais(request)
    form = CodeParentForm(request.POST if request.method == "POST" and not bloque else None)
    if form.is_bound:
        if form.is_valid():
            request.session[SESSION] = form.parent.pk
            return redirect("core:inscription_mot_de_passe")
        _compter_un_echec(request)
        bloque = _trop_d_essais(request)
    return render(request, "core/inscription_parent.html", {"form": form, "bloque": bloque, "etape": 1})


def inscription_mot_de_passe(request):
    """Étape 2 : le parent voit ses enfants et choisit son mot de passe."""
    if request.user.is_authenticated:
        return redirect("core:espace")
    parent = Parent.objects.filter(pk=request.session.get(SESSION), utilisateur__isnull=True,
                                   code_acces__isnull=False).first()
    if parent is None:
        request.session.pop(SESSION, None)
        return redirect("core:inscription")
    enfants = list(parent.enfants.select_related("classe").order_by("prenom"))
    compte = parents.compte_existant(parent)
    bloque = _trop_d_essais(request)
    donnees = request.POST if request.method == "POST" and not bloque else None
    form = CompteExistantForm(donnees, compte=compte) if compte else MotDePasseParentForm(donnees, parent=parent)

    if form.is_bound:
        if form.is_valid():
            with transaction.atomic():
                # Deux clics sur « Créer mon compte » ne créent qu'un compte
                parent = Parent.objects.select_for_update().filter(pk=parent.pk, utilisateur__isnull=True).first()
                if parent is None:
                    return redirect("core:inscription")
                if compte:
                    parents.relier(parent, compte)
                else:
                    compte = parents.creer_compte(parent, form.cleaned_data["mot_de_passe1"])
            request.session.pop(SESSION, None)
            login(request, compte, backend="core.backends.IdentifiantBackend")
            voient = "apparaît" if len(enfants) == 1 else "apparaissent"
            messages.success(request, f"Compte créé. {_prenoms(enfants)} {voient} maintenant dans votre espace parent."
                             if enfants else "Compte créé.", extra_tags="bienvenue")
            return redirect("core:parent_espace")
        if compte:
            _compter_un_echec(request)
            bloque = _trop_d_essais(request)

    return render(request, "core/inscription_parent.html", {
        "form": form, "bloque": bloque, "etape": 2, "parent": parent, "enfants": enfants, "compte_existant": bool(compte),
    })


# ─────────────────────────── Espace parent ───────────────────────────
def _bulletin(eleve):
    """Notes de l'année de l'élève : une ligne par matière, une case par trimestre."""
    notes = Note.objects.filter(eleve=eleve, annee_scolaire=choices.annee_scolaire_courante()) \
        .select_related("eleve", "eleve__classe", "professeur")
    lignes = []
    for groupe in outils_notes.grouper(notes):
        for matiere in groupe["matieres"]:
            ligne = matiere["lignes"][0]
            lignes.append({"matiere": matiere["matiere"], "professeurs": matiere["professeurs"],
                           "cellules": ligne["cellules"], "moyenne": ligne["moyenne"]})
    lignes.sort(key=lambda l: l["matiere"])
    moyennes = [outils_notes._moyenne([l["cellules"][i].note if l["cellules"][i] else None for l in lignes])
                for i in range(len(choices.PERIODES))]
    return lignes, moyennes, outils_notes._moyenne([l["moyenne"] for l in lignes])


@login_required
def parent_espace(request, pk=None):
    parent = parent_de(request.user)
    if parent is None:
        return redirect("core:espace")
    enfants = list(parent.enfants.select_related("classe", "classe__section").order_by("prenom", "nom"))
    enfant = None
    if pk is not None:
        enfant = next((e for e in enfants if e.pk == pk), None)
        if enfant is None:
            raise Http404  # un parent ne voit que ses enfants
    elif enfants:
        enfant = enfants[0]

    contexte = {"parent": parent, "enfants": enfants, "enfant": enfant, "periodes": choices.PERIODES,
                "annee": choices.annee_scolaire_courante()}
    if enfant is not None:
        lignes, moyennes, moyenne_generale = _bulletin(enfant)
        paiements = list(enfant.paiements.all())
        contexte.update({
            "lignes": lignes, "moyennes": moyennes, "moyenne_generale": moyenne_generale,
            "paiements": paiements,
            "total_paye": sum((p.montant for p in paiements if p.statut == "Payé"), 0),
        })
    return render(request, "core/parent_espace.html", contexte)


# ─────────────────────────── Secrétariat ───────────────────────────
A_REMETTRE = "code"
ACTIFS = "compte"


@acces_requis("parents")
def parent_liste(request):
    filtre = request.GET.get("statut", "")
    q = request.GET.get("q", "").strip()
    familles = Parent.objects.select_related("utilisateur").prefetch_related("enfants", "enfants__classe")
    if filtre == A_REMETTRE:
        familles = familles.filter(utilisateur__isnull=True)
    elif filtre == ACTIFS:
        familles = familles.filter(utilisateur__isnull=False)
    if q:
        familles = familles.filter(Q(nom__icontains=q) | Q(telephone__icontains=q) | Q(enfants__nom__icontains=q)
                                   | Q(enfants__prenom__icontains=q) | Q(code_acces__icontains=q)).distinct()
    compte = Parent.objects.aggregate(tous=Count("pk"), actifs=Count("pk", filter=Q(utilisateur__isnull=False)))
    onglets = [("", "Toutes", compte["tous"]), (A_REMETTRE, "Code à remettre", compte["tous"] - compte["actifs"]),
               (ACTIFS, "Compte actif", compte["actifs"])]
    return render(request, "core/parent_liste.html", {"familles": familles, "onglets": onglets, "filtre": filtre, "q": q})


@acces_requis("parents")
def parent_acces(request, pk):
    """Fiche à remettre à la famille : le code d'accès et l'adresse de la page « Créer mon compte »."""
    parent = get_object_or_404(Parent.objects.select_related("utilisateur"), pk=pk)
    compte = parent.utilisateur
    return render(request, "core/parent_acces.html", {
        "parent": parent,
        "enfants": parent.enfants.select_related("classe").order_by("prenom"),
        "adresse_inscription": request.build_absolute_uri(reverse("core:inscription")),
        "adresse_connexion": request.build_absolute_uri(reverse("core:login")),
        "mot_de_passe": request.session.pop(_CLE_MOT_DE_PASSE.format(parent.pk), None),
        "peut_reinitialiser": compte is not None and parents.peut_reinitialiser(compte),
    })


@require_POST
@acces_requis("parents", ecriture=True)
def parent_nouveau_code(request, pk):
    """Code perdu : un nouveau code remplace l'ancien, qui ne sert plus."""
    parent = get_object_or_404(Parent, pk=pk)
    if parent.utilisateur_id:
        messages.error(request, "Cette famille a déjà son compte. Donnez-lui plutôt un nouveau mot de passe.")
    else:
        parents.donner_un_code(parent)
        messages.success(request, "Nouveau code créé. L'ancien code ne fonctionne plus.")
    return redirect("core:parent_acces", pk=pk)


@require_POST
@acces_requis("parents", ecriture=True)
def parent_nouveau_mot_de_passe(request, pk):
    """Mot de passe oublié : un mot de passe provisoire, à changer à la première connexion."""
    parent = get_object_or_404(Parent.objects.select_related("utilisateur"), pk=pk)
    compte = parent.utilisateur
    if compte is None or not parents.peut_reinitialiser(compte):
        messages.error(request, "Ce compte sert aussi au personnel de l'école : la direction s'en occupe.")
    else:
        request.session[_CLE_MOT_DE_PASSE.format(parent.pk)] = nouveau_mot_de_passe(compte)
    return redirect("core:parent_acces", pk=pk)


@require_POST
@acces_requis("parents", ecriture=True)
def eleve_acces_parent(request, pk):
    """Depuis la fiche de l'élève : relie l'élève à sa famille (par le téléphone) et prépare le code."""
    eleve = get_object_or_404(filtrer(request.user, "eleves", Eleve.objects.all()), pk=pk)
    parent = parents.parent_de_l_eleve(eleve)
    if parent is None:
        messages.error(request, "Ajoutez d'abord le téléphone du parent sur la fiche de l'élève (bouton Modifier).")
        return redirect("core:eleve_fiche", pk=pk)
    return redirect("core:parent_acces", pk=parent.pk)


def resume_pour_le_tableau_de_bord(user):
    """Nombre de codes remis qui n'ont pas encore servi (None si l'utilisateur ne suit pas les comptes parents)."""
    if not peut(user, "parents"):
        return None
    return parents.codes_a_remettre().count()
