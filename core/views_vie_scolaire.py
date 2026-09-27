# core/views_vie_scolaire.py
# Vie scolaire (cahier des charges, section G). Le surveillant fait l'appel du
# matin sur son téléphone et signale les incidents ; un professeur peut faire
# l'appel de ses classes et signaler un incident. Le censeur (ou la direction
# de la section) justifie les absences, décide des sanctions et convoque les
# parents. Les parents voient les absences, les retards et les incidents
# traités dans leur espace.
from datetime import date as Date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import choices, notifications
from .classes import dans_l_ordre
from .forms import AlerteSanteForm, IncidentForm, IncidentTraitementForm
from .models import Absence, AlerteSante, Appel, Classe, Eleve, Incident, Parent
from .roles import acces_requis, filtrer, peut, peut_traiter_vie_scolaire, professeur_de


def classes_de_l_appel(user):
    """Les classes dont l'utilisateur fait l'appel : sa section (vie scolaire), ou ses classes (professeur)."""
    if peut(user, "vie_scolaire", ecriture=True):
        return filtrer(user, "vie_scolaire", Classe.objects.select_related("section"), ecriture=True, chemin="section")
    professeur = professeur_de(user)
    if professeur is not None:
        return professeur.classes.select_related("section")
    return Classe.objects.none()


def fait_l_appel(user):
    return classes_de_l_appel(user).exists()


def _date_passee(texte):
    """La date demandée (AAAA-MM-JJ), ou aujourd'hui si elle est absente, fausse ou dans le futur."""
    aujourd_hui = timezone.localdate()
    try:
        jour = Date.fromisoformat(texte or "")
    except ValueError:
        return aujourd_hui
    return min(jour, aujourd_hui)


def _jour(request, user):
    """Le jour de l'appel : aujourd'hui, ou un jour passé pour le censeur et la direction (correction)."""
    jour = _date_passee(request.POST.get("date") or request.GET.get("date"))
    if jour != timezone.localdate() and not any(peut_traiter_vie_scolaire(user, s) for s in _sections(user)):
        return timezone.localdate()
    return jour


def _sections(user):
    return {c.section for c in classes_de_l_appel(user) if c.section_id}


# ─────────────────────────── Appel du matin ───────────────────────────
@login_required
def appel_choix(request):
    classes = dans_l_ordre(classes_de_l_appel(request.user))
    if not classes and not peut(request.user, "vie_scolaire"):
        raise PermissionDenied
    jour = timezone.localdate()
    faits = {a.classe_id: a for a in Appel.objects.filter(classe__in=classes, date=jour).select_related("fait_par")}
    absents = dict(Absence.objects.filter(eleve__classe__in=classes, date=jour).order_by()
                   .values_list("eleve__classe").annotate(n=Count("pk")))
    for classe in classes:
        classe.appel = faits.get(classe.pk)
        classe.nb_absents_retards = absents.get(classe.pk, 0)
    return render(request, "core/appel_choix.html", {
        "classes": classes, "jour": jour, "nb_faits": len(faits),
        "vie_scolaire": peut(request.user, "vie_scolaire"),
    })


@login_required
def appel(request, pk):
    classe = get_object_or_404(classes_de_l_appel(request.user), pk=pk)
    jour = _jour(request, request.user)
    eleves = list(classe.eleves.order_by("nom", "prenom"))
    existantes = {a.eleve_id: a for a in Absence.objects.filter(eleve__in=eleves, date=jour)}

    if request.method == "POST":
        compte = {choices.PRESENT: 0, choices.RETARD: 0, choices.ABSENCE: 0}
        with transaction.atomic():
            for eleve in eleves:
                statut = request.POST.get(f"e{eleve.pk}", choices.PRESENT)
                if statut not in compte:
                    statut = choices.PRESENT
                compte[statut] += 1
                absence = existantes.get(eleve.pk)
                if statut == choices.PRESENT:
                    if absence is not None:
                        absence.delete()
                    continue
                if absence is None:
                    absence = Absence(eleve=eleve, date=jour, signalee_par=request.user)
                elif absence.type != statut:
                    absence.justifiee, absence.motif = False, ""
                absence.type = statut
                minutes = request.POST.get(f"m{eleve.pk}", "").strip()
                absence.minutes_retard = int(minutes) if statut == choices.RETARD and minutes.isdigit() else None
                absence.save()
                notifications.pour_absence(absence)
            Appel.objects.update_or_create(classe=classe, date=jour, defaults={"fait_par": request.user})
        messages.success(request, f"Appel de {classe} enregistré : {compte[choices.ABSENCE]} absent(s), "
                                  f"{compte[choices.RETARD]} retard(s), {compte[choices.PRESENT]} présent(s).")
        return redirect("core:appel_choix")

    lignes = [(eleve, existantes.get(eleve.pk)) for eleve in eleves]
    return render(request, "core/appel.html", {
        "classe": classe, "jour": jour, "lignes": lignes,
        "appel_fait": Appel.objects.filter(classe=classe, date=jour).select_related("fait_par").first(),
        "statuts": [choices.PRESENT, choices.RETARD, choices.ABSENCE],
    })


# ─────────────────────────── Tableau du censeur ───────────────────────────
@acces_requis("vie_scolaire")
def tableau(request):
    user = request.user
    jour = _date_passee(request.GET.get("date"))
    absences = list(filtrer(user, "vie_scolaire", Absence.objects.filter(date=jour)
                            .select_related("eleve", "eleve__classe", "eleve__classe__section", "signalee_par")))
    for a in absences:
        a.peut_traiter = peut_traiter_vie_scolaire(user, a.eleve.classe.section if a.eleve.classe else None)
    tous = request.GET.get("incidents") == "tous"
    incidents = filtrer(user, "vie_scolaire", Incident.objects.select_related("eleve", "eleve__classe", "signale_par"))
    ouverts = incidents.exclude(statut=choices.INCIDENT_CLOS)
    classes = filtrer(user, "vie_scolaire", Classe.objects.all(), chemin="section")
    return render(request, "core/vie_scolaire.html", {
        "jour": jour, "aujourd_hui": timezone.localdate(),
        "absences": absences,
        "nb_absents": sum(1 for a in absences if a.type == choices.ABSENCE),
        "nb_justifiees": sum(1 for a in absences if a.type == choices.ABSENCE and a.justifiee),
        "nb_retards": sum(1 for a in absences if a.type == choices.RETARD),
        "incidents": (incidents if tous else ouverts)[:100], "tous": tous,
        "nb_a_traiter": ouverts.filter(statut=choices.INCIDENT_SIGNALE).count(),
        "nb_ouverts": ouverts.count(),
        "convocations": ouverts.filter(convocation_le__gte=timezone.now()).order_by("convocation_le"),
        "malades": _alertes_visibles(user).filter(cree_le__date=jour),
        "nb_classes": classes.count(),
        "nb_appels": Appel.objects.filter(classe__in=classes, date=jour).count(),
        "fait_l_appel": fait_l_appel(user),
    })


@require_POST
@acces_requis("vie_scolaire", ecriture=True)
def absence_justifier(request, pk):
    absence = get_object_or_404(filtrer(request.user, "vie_scolaire", Absence.objects.select_related("eleve__classe")), pk=pk)
    if not peut_traiter_vie_scolaire(request.user, absence.eleve.classe.section if absence.eleve.classe else None):
        raise PermissionDenied
    absence.justifiee = request.POST.get("justifiee") == "oui"
    absence.motif = request.POST.get("motif", "").strip()[:200]
    absence.save(update_fields=["justifiee", "motif", "mise_a_jour"])
    notifications.pour_absence(absence)
    messages.success(request, f"{absence.type} de {absence.eleve.prenom} {absence.eleve.nom} : "
                              f"{'justifiée' if absence.justifiee else 'non justifiée'}.")
    return redirect(f"{reverse('core:vie_scolaire')}?date={absence.date.isoformat()}")


# ─────────────────────────── Incidents ───────────────────────────
def _eleves_signalables(user):
    return Eleve.objects.filter(classe__in=classes_de_l_appel(user)).select_related("classe").order_by("nom", "prenom")


@login_required
def incident_nouveau(request):
    eleves = _eleves_signalables(request.user)
    if not fait_l_appel(request.user):
        raise PermissionDenied
    initial = {"date": timezone.localdate(), "eleve": request.GET.get("eleve")}
    form = IncidentForm(request.POST or None, eleves=eleves, initial=initial)
    if form.is_valid():
        incident = form.save(commit=False)
        incident.signale_par = request.user
        incident.save()
        messages.success(request, f"Incident de {incident.eleve.prenom} {incident.eleve.nom} transmis au censeur.")
        if peut(request.user, "vie_scolaire"):
            return redirect("core:incident_fiche", pk=incident.pk)
        return redirect("core:appel_choix")
    return render(request, "core/generic_form.html", {
        "form": form, "titre": "Signaler un incident", "icone_titre": "attention",
    })


def _incident_visible(request, pk):
    return get_object_or_404(filtrer(request.user, "vie_scolaire", Incident.objects.select_related(
        "eleve", "eleve__classe", "eleve__classe__section", "signale_par", "traite_par")), pk=pk)


@acces_requis("vie_scolaire")
def incident_fiche(request, pk):
    incident = _incident_visible(request, pk)
    section = incident.eleve.classe.section if incident.eleve.classe else None
    traite = peut_traiter_vie_scolaire(request.user, section)
    form = IncidentTraitementForm(request.POST or None, instance=incident) if traite else None
    if form is not None and request.method == "POST" and form.is_valid():
        incident = form.save(commit=False)
        incident.traite_par = request.user
        incident.save()
        notifications.pour_incident(incident)
        messages.success(request, "Suite enregistrée. Les parents sont informés : ils la voient dans leur espace."
                         if incident.informer_parents else "Suite enregistrée. Les parents ne sont pas informés.")
        return redirect("core:incident_fiche", pk=incident.pk)
    autres = Incident.objects.filter(eleve=incident.eleve).exclude(pk=incident.pk)[:5]
    message = f"Institution Les Nénuphars : au sujet de {incident.eleve.prenom} {incident.eleve.nom}. {incident.description}"
    if incident.sanction:
        message += f" Suite donnée : {incident.sanction}."
    if incident.convocation_le:
        message += f" Vous êtes convoqué(e) à l'école le {notifications.quand(incident.convocation_le)}."
    debut, fin = choices.dates_du_trimestre(choices.trimestre_du_jour(), choices.annee_scolaire_courante())
    assiduite = Absence.objects.filter(eleve=incident.eleve, date__range=(debut, fin)).aggregate(
        absences=Count("pk", filter=Q(type=choices.ABSENCE)), retards=Count("pk", filter=Q(type=choices.RETARD)))
    return render(request, "core/incident_fiche.html", {
        "incident": incident, "form": form, "autres": autres, "assiduite": assiduite,
        "comptes_parents": Parent.objects.filter(enfants=incident.eleve, utilisateur__isnull=False).count(),
        "whatsapp": notifications.lien_whatsapp(incident.eleve.telephone_parent, message),
    })


@acces_requis("vie_scolaire")
def incident_convocation(request, pk):
    """Convocation des parents à imprimer et à remettre (ou à photographier pour WhatsApp)."""
    incident = _incident_visible(request, pk)
    if incident.convocation_le is None:
        messages.error(request, "Indiquez d'abord la date de la convocation.")
        return redirect("core:incident_fiche", pk=pk)
    return render(request, "core/incident_convocation.html", {"incident": incident})


# ─────────────────────────── Élève malade ───────────────────────────
def _alertes_visibles(user):
    """Les alertes des élèves dont on fait l'appel, et celles de sa section pour la vie scolaire."""
    return AlerteSante.objects.filter(
        Q(eleve__classe__in=classes_de_l_appel(user))
        | Q(pk__in=filtrer(user, "vie_scolaire", AlerteSante.objects.all()).values("pk"))
    ).select_related("eleve", "eleve__classe", "signale_par")


@login_required
def sante_nouvelle(request):
    """Un élève tombe malade à l'école : ses parents reçoivent une notification tout de suite."""
    if not fait_l_appel(request.user):
        raise PermissionDenied
    form = AlerteSanteForm(request.POST or None, eleves=_eleves_signalables(request.user),
                           initial={"eleve": request.GET.get("eleve")})
    if form.is_valid():
        alerte = form.save(commit=False)
        alerte.signale_par = request.user
        alerte.save()
        notifications.pour_alerte_sante(alerte)
        return redirect("core:sante_fiche", pk=alerte.pk)
    return render(request, "core/generic_form.html", {
        "form": form, "titre": "Élève malade", "icone_titre": "sante",
        "intro": "Les parents reçoivent une notification dès que vous enregistrez. "
                 "Si c'est urgent, appelez aussi la famille.",
    })


@login_required
def sante_fiche(request, pk):
    alerte = get_object_or_404(_alertes_visibles(request.user), pk=pk)
    eleve = alerte.eleve
    message = (f"Institution Les Nénuphars : {eleve.prenom} {eleve.nom} est malade à l'école. "
               f"{alerte.description} Ce que fait l'école : {alerte.mesure}.")
    return render(request, "core/sante_fiche.html", {
        "alerte": alerte,
        "comptes_parents": Parent.objects.filter(enfants=eleve, utilisateur__isnull=False).count(),
        "whatsapp": notifications.lien_whatsapp(eleve.telephone_parent, message),
    })
