# site_public/forms.py
from django import forms

from core import photos
from core.forms import PreinscriptionForm
from core.models import MessageContact
from core.telephone import normaliser_telephone


class PiegeARobotsMixin(forms.Form):
    """Champ caché aux visiteurs : seul un robot le remplit, et sa demande est ignorée."""
    site_web = forms.CharField(required=False, label="Ne remplissez pas ce champ",
                               widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}))

    @property
    def est_un_robot(self):
        return bool(self.data.get("site_web"))


class PreinscriptionPubliqueForm(PiegeARobotsMixin, PreinscriptionForm):
    class Meta(PreinscriptionForm.Meta):
        fields = [*PreinscriptionForm.Meta.fields, "acte_naissance", "dernier_bulletin"]
        labels = {**PreinscriptionForm.Meta.labels,
                  "acte_naissance": "Acte de naissance", "dernier_bulletin": "Dernier bulletin"}
        widgets = {
            **PreinscriptionForm.Meta.widgets,
            "acte_naissance": forms.FileInput(attrs={"accept": "image/*,application/pdf"}),
            "dernier_bulletin": forms.FileInput(attrs={"accept": "image/*,application/pdf"}),
        }

    def clean_acte_naissance(self):
        return photos.preparer_document(self.cleaned_data.get("acte_naissance"))

    def clean_dernier_bulletin(self):
        return photos.preparer_document(self.cleaned_data.get("dernier_bulletin"))


class MessageContactForm(PiegeARobotsMixin, forms.ModelForm):
    class Meta:
        model = MessageContact
        fields = ["nom", "telephone", "email", "message"]
        labels = {"nom": "Votre nom", "telephone": "Téléphone", "email": "E-mail (facultatif)", "message": "Votre message"}
        widgets = {
            "nom": forms.TextInput(attrs={"autocomplete": "name"}),
            "telephone": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel", "placeholder": "ex : 3712 3456"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "message": forms.Textarea(attrs={"rows": 5, "maxlength": 2000}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["telephone"].required = True

    def clean_telephone(self):
        telephone = self.cleaned_data["telephone"].strip()
        if len(normaliser_telephone(telephone)) < 11:
            raise forms.ValidationError("Numéro incomplet : 8 chiffres, par exemple 3712 3456.")
        return telephone

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) > 2000:
            raise forms.ValidationError("Message trop long (2 000 caractères au plus).")
        return message
