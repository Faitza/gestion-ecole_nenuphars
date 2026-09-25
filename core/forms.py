# core/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from .models import Eleve, Professeur, Employe, Paiement, Note, Classe
from . import roles


def _ctrl(widget_cls, **kwargs):
    attrs = kwargs.pop("attrs", {})
    attrs.setdefault("class", "form-control")
    return widget_cls(attrs=attrs, **kwargs)


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Téléphone, e-mail ou nom d'utilisateur",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "ex : 3712 3456", "autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Mot de passe", "autocomplete": "current-password"}),
    )
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Identifiant ou mot de passe incorrect.",
        "inactive": "Ce compte est désactivé. Adressez-vous au secrétariat.",
    }


class MotDePasseForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            champ.widget.attrs.setdefault("class", "form-control")


class ClasseForm(forms.ModelForm):
    class Meta:
        model = Classe
        fields = ["nom", "section", "cycle", "annee_scolaire"]
        widgets = {
            "nom": _ctrl(forms.TextInput, attrs={"class": "form-control", "placeholder": "ex: 7ème AF"}),
            "section": _ctrl(forms.Select),
            "cycle": _ctrl(forms.Select),
            "annee_scolaire": _ctrl(forms.TextInput, attrs={"class": "form-control", "placeholder": "ex: 2026-2027"}),
        }


class EleveForm(forms.ModelForm):
    class Meta:
        model = Eleve
        fields = ["nom", "prenom", "date_naissance", "genre", "classe", "nom_parent_tuteur", "telephone_parent", "email", "adresse"]
        widgets = {
            "nom": _ctrl(forms.TextInput),
            "prenom": _ctrl(forms.TextInput),
            "date_naissance": _ctrl(forms.DateInput, attrs={"type": "date", "class": "form-control"}),
            "genre": _ctrl(forms.Select),
            "classe": _ctrl(forms.Select),
            "nom_parent_tuteur": _ctrl(forms.TextInput),
            "telephone_parent": _ctrl(forms.TextInput),
            "email": _ctrl(forms.EmailInput),
            "adresse": _ctrl(forms.Textarea, attrs={"class": "form-control", "rows": 2}),
        }


class ProfesseurForm(forms.ModelForm):
    classes = forms.ModelMultipleChoiceField(
        queryset=Classe.objects.all(), required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-control", "size": 6}),
        label="Classe(s) enseignée(s)",
    )

    class Meta:
        model = Professeur
        fields = ["nom", "prenom", "email", "telephone", "section", "matiere_principale", "classes", "date_embauche"]
        widgets = {
            "section": _ctrl(forms.Select),
            "nom": _ctrl(forms.TextInput),
            "prenom": _ctrl(forms.TextInput),
            "email": _ctrl(forms.EmailInput),
            "telephone": _ctrl(forms.TextInput),
            "matiere_principale": _ctrl(forms.Select),
            "date_embauche": _ctrl(forms.DateInput, attrs={"type": "date", "class": "form-control"}),
        }


class EmployeForm(forms.ModelForm):
    class Meta:
        model = Employe
        fields = ["nom", "prenom", "poste", "section", "email", "telephone", "salaire", "date_embauche"]
        widgets = {
            "nom": _ctrl(forms.TextInput),
            "prenom": _ctrl(forms.TextInput),
            "poste": _ctrl(forms.Select),
            "section": _ctrl(forms.Select),
            "email": _ctrl(forms.EmailInput),
            "telephone": _ctrl(forms.TextInput),
            "salaire": _ctrl(forms.NumberInput),
            "date_embauche": _ctrl(forms.DateInput, attrs={"type": "date", "class": "form-control"}),
        }


class PaiementForm(forms.ModelForm):
    class Meta:
        model = Paiement
        fields = ["eleve", "montant", "type_paiement", "methode_paiement", "statut"]
        widgets = {
            "eleve": _ctrl(forms.Select),
            "montant": _ctrl(forms.NumberInput),
            "type_paiement": _ctrl(forms.Select),
            "methode_paiement": _ctrl(forms.Select),
            "statut": _ctrl(forms.Select),
        }


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["eleve", "professeur", "matiere", "note", "periode", "annee_scolaire"]
        widgets = {
            "eleve": _ctrl(forms.Select),
            "professeur": _ctrl(forms.Select),
            "matiere": _ctrl(forms.Select),
            "note": _ctrl(forms.NumberInput, attrs={"class": "form-control", "min": 0, "max": 100, "step": "0.01"}),
            "periode": _ctrl(forms.Select),
            "annee_scolaire": _ctrl(forms.TextInput, attrs={"class": "form-control", "placeholder": "ex: 2026-2027"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            # Une direction de section ne note que les élèves de sa section
            self.fields["eleve"].queryset = roles.filtrer(
                user, "notes", Eleve.objects.all(), ecriture=True, chemin="classe__section"
            )

    def clean_note(self):
        note = self.cleaned_data["note"]
        if not (0 <= note <= 100):
            raise forms.ValidationError("La note doit être comprise entre 0 et 100.")
        return note
