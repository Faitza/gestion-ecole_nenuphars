# core/notifications.py
# Notifications des parents. Chaque événement qui concerne un enfant (absence
# ou retard à l'appel, incident dont le censeur veut informer les parents,
# convocation, élève malade, bulletin publié) et chaque annonce crée une
# notification pour chacun de ses parents. Le parent les voit dans le menu
# « Notifications », avec le nombre de nouvelles, et à la connexion.
#
# Les notifications restent sur le site : pour un message urgent, les pages du
# censeur proposent aussi « Prévenir par WhatsApp », qui ouvre WhatsApp avec le
# message déjà écrit.
from django.db.models import Count
from django.utils import timezone
from django.utils.formats import date_format

from . import choices
from .models import Eleve, Notification, Parent


def _prenom(eleve):
    return eleve.prenom or str(eleve)


def _e(eleve):
    """Accord : « absente » pour une fille, « absent » pour un garçon."""
    return "e" if eleve.genre == "Féminin" else ""


def quand(moment):
    return date_format(timezone.localtime(moment), r"l j F \à G \h i")


def _pour_chaque_parent(eleve, source, categorie, titre, texte):
    """Crée ou met à jour la notification de chaque parent pour cette source (absence, incident...).

    Une notification déjà lue redevient nouvelle seulement si ce qu'elle dit a changé.
    """
    champ, objet = source
    for parent in Parent.objects.filter(enfants=eleve):
        notification = Notification.objects.filter(parent=parent, **{champ: objet}).first()
        if notification is None:
            Notification.objects.create(parent=parent, eleve=eleve, categorie=categorie, titre=titre, texte=texte,
                                        **{champ: objet})
        elif (notification.categorie, notification.titre, notification.texte) != (categorie, titre, texte):
            notification.categorie, notification.titre, notification.texte = categorie, titre, texte
            notification.cree_le, notification.lue_le = timezone.now(), None
            notification.save()


def pour_absence(absence):
    eleve, jour = absence.eleve, date_format(absence.date, "l j F")
    if absence.type == choices.RETARD:
        minutes = f" de {absence.minutes_retard} min" if absence.minutes_retard else ""
        categorie, titre = choices.NOTIF_RETARD, f"{_prenom(eleve)} est arrivé{_e(eleve)} en retard{minutes} le {jour}"
    else:
        categorie, titre = choices.NOTIF_ABSENCE, f"{_prenom(eleve)} est absent{_e(eleve)} le {jour}"
    texte = "Si ce n'est pas justifié, adressez-vous à la vie scolaire de l'école."
    if absence.justifiee:
        texte = f"Justifié{'e' if absence.type == choices.ABSENCE else ''}" + (f" : {absence.motif}" if absence.motif else ".")
    _pour_chaque_parent(absence.eleve, ("absence", absence), categorie, titre, texte)


def pour_incident(incident):
    """Seulement si le censeur a coché « Informer les parents » ; sinon la notification est retirée."""
    if not incident.informer_parents:
        Notification.objects.filter(incident=incident).delete()
        return
    prenom = _prenom(incident.eleve)
    texte = incident.description
    if incident.sanction:
        texte += f"\nSuite donnée : {incident.sanction}"
    if incident.convocation_le:
        categorie = choices.NOTIF_CONVOCATION
        titre = f"Vous êtes convoqué(e) à l'école le {quand(incident.convocation_le)}, au sujet de {prenom}"
    else:
        categorie, titre = choices.NOTIF_COMPORTEMENT, f"Comportement de {prenom} à l'école"
    _pour_chaque_parent(incident.eleve, ("incident", incident), categorie, titre, texte)


def pour_alerte_sante(alerte):
    eleve = alerte.eleve
    titre = f"{_prenom(eleve)} est malade à l'école"
    texte = (f"{alerte.description}\nCe que fait l'école : {alerte.mesure}.\n"
             f"Signalé le {quand(alerte.cree_le)}. Vous pouvez appeler l'école.")
    _pour_chaque_parent(alerte.eleve, ("alerte_sante", alerte), choices.NOTIF_SANTE, titre, texte)


def pour_bulletins(bulletins):
    """Après la validation : le bulletin de chaque élève est disponible pour ses parents."""
    for bulletin in bulletins:
        titre = f"Le bulletin du {bulletin.periode.lower()} de {_prenom(bulletin.eleve)} est disponible"
        texte = "Vous pouvez le lire, l'imprimer ou le télécharger en PDF ou en image."
        _pour_chaque_parent(bulletin.eleve, ("bulletin", bulletin), choices.NOTIF_BULLETIN, titre, texte)


def retirer_bulletins(bulletins):
    Notification.objects.filter(bulletin__in=bulletins).delete()


def pour_annonce(annonce):
    """Chaque parent concerné (école, section ou classe) reçoit la notification une seule fois."""
    eleves = Eleve.objects.all()
    if annonce.classe_id:
        eleves = eleves.filter(classe=annonce.classe_id)
    elif annonce.section_id:
        eleves = eleves.filter(classe__section=annonce.section_id)
    concernes = set(Parent.objects.filter(enfants__in=eleves).values_list("pk", flat=True))
    existantes = dict(Notification.objects.filter(annonce=annonce).values_list("parent_id", "pk"))
    Notification.objects.filter(annonce=annonce).exclude(parent__in=concernes).delete()
    Notification.objects.filter(annonce=annonce).update(titre=annonce.titre, texte=annonce.texte)
    Notification.objects.bulk_create([
        Notification(parent_id=pk, categorie=choices.NOTIF_ANNONCE, titre=annonce.titre, texte=annonce.texte,
                     annonce=annonce, cree_le=annonce.publiee_le)
        for pk in concernes - set(existantes)
    ])


# ─────────────────────────── Côté parent ───────────────────────────
def non_lues(parent):
    return parent.notifications.filter(lue_le__isnull=True)


def compte_par_categorie(parent):
    return dict(non_lues(parent).order_by().values_list("categorie").annotate(n=Count("pk")))


PHRASES = [
    (choices.NOTIF_SANTE, "alerte santé", "alertes santé"),
    (choices.NOTIF_CONVOCATION, "convocation", "convocations"),
    (choices.NOTIF_COMPORTEMENT, "message sur le comportement", "messages sur le comportement"),
    (choices.NOTIF_ABSENCE, "absence", "absences"),
    (choices.NOTIF_RETARD, "retard", "retards"),
    (choices.NOTIF_BULLETIN, "bulletin publié", "bulletins publiés"),
    (choices.NOTIF_ANNONCE, "annonce", "annonces"),
]


def phrase(compte):
    """« 1 alerte santé, 2 absences et 1 annonce » (ou "" s'il n'y a rien)."""
    morceaux = [f"{compte[c]} {un if compte[c] == 1 else plusieurs}" for c, un, plusieurs in PHRASES if compte.get(c)]
    if not morceaux:
        return ""
    return morceaux[0] if len(morceaux) == 1 else ", ".join(morceaux[:-1]) + " et " + morceaux[-1]


def marquer_lues(parent, **filtre):
    """Tout ce que le parent vient de voir (ou tout, sans filtre) n'est plus nouveau."""
    non_lues(parent).filter(**filtre).update(lue_le=timezone.now())


def lien_whatsapp(telephone, message):
    """Ouvre WhatsApp avec le message déjà écrit, pour le numéro du parent (ou "" sans numéro)."""
    from urllib.parse import quote

    from .telephone import normaliser_telephone
    numero = normaliser_telephone(telephone)
    return f"https://wa.me/{numero}?text={quote(message)}" if numero else ""
