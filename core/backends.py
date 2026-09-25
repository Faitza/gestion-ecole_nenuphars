# core/backends.py
# Connexion avec le nom d'utilisateur, l'adresse e-mail ou le numéro de téléphone.
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from .telephone import normaliser_telephone


class IdentifiantBackend(ModelBackend):
    """Un seul champ « identifiant » pour tous les rôles."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        Utilisateur = get_user_model()
        identifiant = (username if username is not None else kwargs.get(Utilisateur.USERNAME_FIELD) or "").strip()
        if not identifiant or password is None:
            return None

        utilisateur = self._trouver(Utilisateur, identifiant)
        if utilisateur is None:
            # Même temps de calcul qu'un vrai compte, pour ne pas révéler qui existe
            Utilisateur().set_password(password)
            return None
        if utilisateur.check_password(password) and self.user_can_authenticate(utilisateur):
            return utilisateur
        return None

    @staticmethod
    def _trouver(Utilisateur, identifiant):
        compte = Utilisateur.objects.filter(username=identifiant).first()
        if compte:
            return compte
        if "@" in identifiant:
            comptes = list(Utilisateur.objects.filter(email__iexact=identifiant)[:2])
            return comptes[0] if len(comptes) == 1 else None
        telephone = normaliser_telephone(identifiant)
        if len(telephone) >= 8:
            return Utilisateur.objects.filter(telephone=telephone).first()
        return None
