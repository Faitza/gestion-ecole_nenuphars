from django import forms
from django.contrib.auth.forms import AuthenticationForm

from core.telephone import normaliser_telephone

from .models import Ecole


def _style(formulaire):
    for champ in formulaire.fields.values():
        if not isinstance(champ.widget, forms.CheckboxInput):
            champ.widget.attrs.setdefault("class", "form-control")


class ConnexionForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Identifiant ou mot de passe incorrect.",
        "inactive": "Ce compte est désactivé.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Identifiant"
        _style(self)

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        # Seuls les administrateurs de la plateforme gèrent les écoles
        if not user.is_superuser:
            raise forms.ValidationError(self.error_messages["invalid_login"], code="invalid_login")


CHAMPS_ECOLE = ["nom", "nom_court", "sous_domaine", "ville", "adresse", "telephones", "whatsapp", "courriel",
                "accroche", "presentation"]


class EcoleForm(forms.ModelForm):
    class Meta:
        model = Ecole
        fields = CHAMPS_ECOLE
        widgets = {"telephones": forms.Textarea(attrs={"rows": 2}), "presentation": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sous_domaine"].widget.attrs.update(
            {"autocapitalize": "none", "autocomplete": "off", "spellcheck": "false"})
        if self.instance.pk:
            # L'adresse est déjà connue des familles : elle ne change plus ici
            self.fields["sous_domaine"].disabled = True
        _style(self)

    def clean_sous_domaine(self):
        return (self.cleaned_data.get("sous_domaine") or "").strip().lower()


class NouvelleEcoleForm(EcoleForm):
    """L'école et le premier compte de sa direction (rôle « Directrice en chef »)."""
    responsable_prenom = forms.CharField(label="Prénom du (de la) responsable", max_length=150)
    responsable_nom = forms.CharField(label="Nom du (de la) responsable", max_length=150)
    responsable_telephone = forms.CharField(
        label="Téléphone du (de la) responsable", max_length=20,
        help_text="Sert d'identifiant de connexion. Ex : 3712 3456.")
    responsable_email = forms.EmailField(label="E-mail du (de la) responsable", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)

    def clean_responsable_telephone(self):
        telephone = normaliser_telephone(self.cleaned_data.get("responsable_telephone"))
        if not telephone:
            raise forms.ValidationError("Numéro de téléphone incomplet.")
        return telephone
