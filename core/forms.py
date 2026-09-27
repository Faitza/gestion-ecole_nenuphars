# core/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.urls import reverse
from .models import (Annonce, Classe, Creneau, Eleve, Employe, Incident, Note, Paiement, Preinscription, Professeur,
                     Section, Utilisateur)
from . import anniversaires, choices, photos, professeurs, roles
from .classes import par_section
from .telephone import normaliser_telephone


class PhotoWidget(forms.ClearableFileInput):
    """Montre la photo actuelle (par la vue protégée) au lieu d'un lien vers le fichier."""
    template_name = "core/widgets/photo.html"
    url_actuelle = None

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["url_actuelle"] = self.url_actuelle
        return context


class PhotoMixin:
    """Réduit la photo envoyée et refuse un fichier trop lourd (voir core/photos.py)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "photo" in self.fields and self.instance.pk and self.instance.photo:
            self.fields["photo"].widget.url_actuelle = reverse(
                "core:photo", args=[self.instance._meta.model_name, self.instance.pk])

    def clean_photo(self):
        return photos.preparer(self.cleaned_data.get("photo"))


def _photo_widget():
    # Sur un téléphone, le bouton propose aussi l'appareil photo
    return PhotoWidget(attrs={"class": "form-control", "accept": "image/*"})


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


class EleveForm(PhotoMixin, forms.ModelForm):
    class Meta:
        model = Eleve
        fields = ["photo", "nom", "prenom", "date_naissance", "genre", "classe", "nom_parent_tuteur", "telephone_parent", "email",
                  "adresse"]
        labels = {"prenom": "Prénom", "date_naissance": "Date de naissance", "nom_parent_tuteur": "Parent ou tuteur",
                  "telephone_parent": "Téléphone du parent", "email": "E-mail"}
        widgets = {
            "photo": _photo_widget(),
            "nom": _ctrl(forms.TextInput),
            "prenom": _ctrl(forms.TextInput),
            "date_naissance": _ctrl(forms.DateInput, attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
            "genre": _ctrl(forms.Select),
            "classe": _ctrl(forms.Select),
            "nom_parent_tuteur": _ctrl(forms.TextInput),
            "telephone_parent": _ctrl(forms.TextInput),
            "email": _ctrl(forms.EmailInput),
            "adresse": _ctrl(forms.Textarea, attrs={"class": "form-control", "rows": 2}),
        }


class ProfesseurForm(PhotoMixin, forms.ModelForm):
    """Informations personnelles du professeur (inscription et modification)."""

    class Meta:
        model = Professeur
        fields = ["photo", "nom", "prenom", "date_naissance", "telephone", "email", "adresse", "diplome",
                  "matiere_principale", "date_embauche"]
        labels = {
            "prenom": "Prénom",
            "date_naissance": "Date de naissance",
            "telephone": "Téléphone (sert d'identifiant)",
            "email": "E-mail (facultatif)",
            "matiere_principale": "Matière principale",
        }
        widgets = {
            "photo": _photo_widget(),
            "nom": _ctrl(forms.TextInput),
            "prenom": _ctrl(forms.TextInput),
            "date_naissance": _ctrl(forms.DateInput, attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
            "telephone": _ctrl(forms.TextInput, attrs={"class": "form-control", "placeholder": "ex : 3712 3456", "inputmode": "tel"}),
            "email": _ctrl(forms.EmailInput),
            "adresse": _ctrl(forms.Textarea, attrs={"class": "form-control", "rows": 2}),
            "diplome": _ctrl(forms.TextInput, attrs={"class": "form-control", "placeholder": "ex : Licence en sciences de l'éducation"}),
            "matiere_principale": _ctrl(forms.Select),
            "date_embauche": _ctrl(forms.DateInput, attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, section=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["telephone"].required = True
        section = section or self.instance.section
        if section is not None and not section.est_secondaire:
            # Au Kindergarten et au primaire, le professeur fait toutes les matières de sa classe
            del self.fields["matiere_principale"]

    def clean_telephone(self):
        telephone = self.cleaned_data["telephone"].strip()
        if len(normaliser_telephone(telephone)) < 11:
            raise forms.ValidationError("Numéro incomplet : 8 chiffres, par exemple 3712 3456.")
        if professeurs.telephone_deja_utilise(telephone, self.instance.utilisateur):
            raise forms.ValidationError("Ce numéro sert déjà d'identifiant à un autre compte.")
        return telephone


class AffectationForm(forms.Form):
    """Kindergarten et primaire : la classe du professeur (et son rôle au Kindergarten)."""
    classe = forms.ModelChoiceField(queryset=Classe.objects.none(), widget=_ctrl(forms.Select), empty_label="Choisir la classe")
    role = forms.ChoiceField(label="Rôle", choices=choices.ROLES_AFFECTATION_CHOICES, initial=choices.ROLE_TITULAIRE,
                             widget=_ctrl(forms.Select))
    remplacer = forms.BooleanField(required=False, label="Remplacer le professeur actuel de cette classe")

    def __init__(self, *args, section, professeur=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.section, self.professeur = section, professeur
        self.fields["classe"].queryset = Classe.objects.filter(section=section)
        self.fields["classe"].label_from_instance = lambda c: professeurs.description_classe(c, section, professeur)
        if section.est_primaire:
            del self.fields["role"]
        else:
            del self.fields["remplacer"]

    def clean(self):
        donnees = super().clean()
        classe = donnees.get("classe")
        if classe is None:
            return donnees
        actives = professeurs.affectations_actives(classe, sauf=self.professeur)
        donnees["a_remplacer"] = []
        if self.section.est_primaire:
            donnees["role"] = choices.ROLE_TITULAIRE
            if actives and not donnees.get("remplacer"):
                self.add_error("remplacer", (
                    f"La classe {classe} a déjà un professeur, {actives[0].professeur}. Au primaire, une classe "
                    "n'a qu'un professeur : cochez la case pour confirmer le remplacement."
                ))
            donnees["a_remplacer"] = actives
        else:
            role = donnees.get("role")
            if len(actives) >= professeurs.PLACES_KINDERGARTEN:
                self.add_error("classe", f"La classe {classe} a déjà ses deux maîtresses.")
            elif role and any(a.role == role for a in actives):
                occupe = next(a for a in actives if a.role == role)
                self.add_error("role", f"La classe {classe} a déjà une {role.lower()} : {occupe.professeur}.")
        return donnees


class CoursForm(forms.Form):
    """Secondaire : une ligne par cours."""
    matiere = forms.ChoiceField(label="Matière", choices=[("", "Matière")] + choices.MATIERES_CHOICES, widget=_ctrl(forms.Select))
    classe = forms.ModelChoiceField(queryset=Classe.objects.none(), empty_label="Classe", widget=_ctrl(forms.Select))
    jour = forms.TypedChoiceField(choices=[("", "Jour")] + choices.JOURS_CHOICES, coerce=int, widget=_ctrl(forms.Select))
    creneau = forms.ModelChoiceField(label="Heure", queryset=Creneau.objects.none(), empty_label="Heure", widget=_ctrl(forms.Select))

    def __init__(self, *args, section, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["classe"].queryset = Classe.objects.filter(section=section)
        self.fields["creneau"].queryset = Creneau.objects.filter(section=section, est_un_cours=True)


class BaseCoursFormSet(forms.BaseFormSet):
    """Refuse un créneau déjà pris dans une classe, ou deux cours du professeur à la même heure."""

    def __init__(self, *args, section, professeur=None, **kwargs):
        self.professeur = professeur
        super().__init__(*args, form_kwargs={"section": section}, **kwargs)

    def lignes(self):
        return [f.cleaned_data for f in self.forms if f.cleaned_data]

    def clean(self):
        if any(self.errors):
            return
        heures_du_professeur, cases_des_classes = set(), set()
        for form in self.forms:
            ligne = form.cleaned_data
            if not ligne:
                continue
            classe, jour, creneau = ligne["classe"], ligne["jour"], ligne["creneau"]
            moment = professeurs.quand(jour, creneau)
            if (jour, creneau.pk) in heures_du_professeur:
                form.add_error(None, f"Deux cours du professeur tombent {moment}.")
            elif (occupe := professeurs.conflit_professeur(self.professeur, jour, creneau)) is not None:
                form.add_error(None, f"Le professeur a déjà un cours {moment} ({occupe.classe}).")
            if (classe.pk, jour, creneau.pk) in cases_des_classes:
                form.add_error(None, f"La classe {classe} a deux cours {moment}.")
            elif (occupe := professeurs.conflit_classe(classe, jour, creneau, self.professeur)) is not None:
                form.add_error(None, (
                    f"La classe {classe} a déjà un cours {moment} : {occupe.matiere} avec {occupe.professeur}."
                ))
            heures_du_professeur.add((jour, creneau.pk))
            cases_des_classes.add((classe.pk, jour, creneau.pk))
        if not self.lignes():
            raise forms.ValidationError("Ajoutez au moins un cours.")


CoursFormSet = forms.formset_factory(CoursForm, formset=BaseCoursFormSet, extra=4)


class EmployeForm(PhotoMixin, forms.ModelForm):
    class Meta:
        model = Employe
        fields = ["photo", "nom", "prenom", "date_naissance", "poste", "section", "email", "telephone", "adresse",
                  "salaire", "date_embauche"]
        labels = {"prenom": "Prénom", "telephone": "Téléphone", "email": "E-mail"}
        widgets = {
            "photo": _photo_widget(),
            "nom": _ctrl(forms.TextInput),
            "prenom": _ctrl(forms.TextInput),
            "date_naissance": _ctrl(forms.DateInput, attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
            "poste": _ctrl(forms.Select),
            "section": _ctrl(forms.Select),
            "email": _ctrl(forms.EmailInput),
            "telephone": _ctrl(forms.TextInput),
            "adresse": _ctrl(forms.Textarea, attrs={"class": "form-control", "rows": 2}),
            "salaire": _ctrl(forms.NumberInput),
            "date_embauche": _ctrl(forms.DateInput, attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
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


# ─────────────────────────── Préinscriptions ───────────────────────────
class PreinscriptionForm(PhotoMixin, forms.ModelForm):
    """Champs de l'élève et du parent, communs au site public et au secrétariat."""

    class Meta:
        model = Preinscription
        fields = ["nom", "prenom", "date_naissance", "genre", "classe_demandee", "ecole_precedente", "photo",
                  "nom_parent", "telephone_parent", "email_parent", "adresse"]
        labels = {
            "ecole_precedente": "École précédente (facultatif)",
            "photo": "Photo d'identité de l'élève",
            "email_parent": "E-mail (facultatif)",
            "adresse": "Adresse (facultatif)",
        }
        help_texts = {"photo": ""}
        widgets = {
            "photo": forms.FileInput(attrs={"accept": "image/*"}),
            "date_naissance": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "nom_parent": forms.TextInput(attrs={"autocomplete": "name"}),
            "telephone_parent": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel", "placeholder": "ex : 3712 3456"}),
            "email_parent": forms.EmailInput(attrs={"autocomplete": "email"}),
            "adresse": forms.TextInput(attrs={"autocomplete": "street-address"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["genre"].choices = [("", "Choisissez"), *choices.GENRES_CHOICES]
        # Classes regroupées par section, dans l'ordre (Kindergarten, primaire, secondaire)
        self.fields["classe_demandee"].choices = [("", "Choisissez la classe")] + [
            (str(section or "Autres classes"), [(c.pk, c.nom) for c in classes])
            for section, classes in par_section(Classe.objects.select_related("section"))
        ]

    def clean_date_naissance(self):
        naissance = self.cleaned_data["date_naissance"]
        if naissance >= anniversaires.aujourd_hui() or not 2 <= anniversaires.age(naissance) <= 25:
            raise forms.ValidationError("Vérifiez la date de naissance de l'élève.")
        return naissance

    def clean_telephone_parent(self):
        telephone = self.cleaned_data["telephone_parent"].strip()
        if len(normaliser_telephone(telephone)) < 11:
            raise forms.ValidationError("Numéro incomplet : 8 chiffres, par exemple 3712 3456.")
        return telephone


class PreinscriptionGestionForm(PreinscriptionForm):
    """Le secrétariat corrige un dossier, ajoute la photo et note le rendez-vous."""

    class Meta(PreinscriptionForm.Meta):
        fields = ["photo", *[f for f in PreinscriptionForm.Meta.fields if f != "photo"], "rendez_vous", "note_interne"]
        labels = PreinscriptionForm.Meta.labels
        help_texts = {"photo": "Photo d'identité, 5 Mo au plus."}
        widgets = {
            **PreinscriptionForm.Meta.widgets,
            "photo": _photo_widget(),
            "rendez_vous": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "note_interne": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            champ.widget.attrs.setdefault("class", "form-control")



# ─────────────────────────── Comptes parents ───────────────────────────
class CodeParentForm(forms.Form):
    code = forms.CharField(label="Code d'accès remis par l'école", max_length=20, widget=forms.TextInput(attrs={
        "class": "form-control", "placeholder": "NEN-XXXX-XX", "autocomplete": "off", "autocapitalize": "characters",
        "autofocus": True,
    }))
    telephone = forms.CharField(label="Téléphone donné à l'inscription", max_length=30, widget=forms.TextInput(attrs={
        "class": "form-control", "placeholder": "ex : 3712 3456", "inputmode": "tel", "autocomplete": "tel",
    }))

    def clean(self):
        from . import parents
        donnees = super().clean()
        self.parent = parents.trouver(donnees.get("code"), donnees.get("telephone"))
        if self.errors:
            return donnees
        if self.parent is None:
            raise forms.ValidationError(
                "Ce code et ce téléphone ne vont pas ensemble, ou le code a déjà servi. "
                "Vérifiez-les, ou demandez un nouveau code au secrétariat.")
        return donnees


class MotDePasseParentForm(forms.Form):
    """Premier mot de passe du parent, avec les règles de mot de passe du site."""
    mot_de_passe1 = forms.CharField(label="Choisissez un mot de passe", strip=False, widget=forms.PasswordInput(attrs={
        "class": "form-control", "autocomplete": "new-password", "autofocus": True}))
    mot_de_passe2 = forms.CharField(label="Confirmez le mot de passe", strip=False, widget=forms.PasswordInput(attrs={
        "class": "form-control", "autocomplete": "new-password"}))

    def __init__(self, *args, parent, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent

    def clean(self):
        from django.contrib.auth import password_validation
        donnees = super().clean()
        mdp1, mdp2 = donnees.get("mot_de_passe1"), donnees.get("mot_de_passe2")
        if mdp1 and mdp2 and mdp1 != mdp2:
            self.add_error("mot_de_passe2", "Les deux mots de passe ne sont pas les mêmes.")
        elif mdp1:
            prenom, _, nom = self.parent.nom.partition(" ")
            futur = Utilisateur(username=self.parent.telephone_normalise, first_name=prenom, last_name=nom)
            try:
                password_validation.validate_password(mdp1, futur)
            except forms.ValidationError as erreur:
                self.add_error("mot_de_passe1", erreur)
        return donnees


class CompteExistantForm(forms.Form):
    """Le téléphone a déjà un compte (un professeur qui est aussi parent) : son mot de passe suffit."""
    mot_de_passe = forms.CharField(label="Mot de passe de votre compte", strip=False, widget=forms.PasswordInput(attrs={
        "class": "form-control", "autocomplete": "current-password", "autofocus": True}))

    def __init__(self, *args, compte, **kwargs):
        super().__init__(*args, **kwargs)
        self.compte = compte

    def clean_mot_de_passe(self):
        mot_de_passe = self.cleaned_data["mot_de_passe"]
        if not self.compte.check_password(mot_de_passe):
            raise forms.ValidationError("Mot de passe incorrect.")
        return mot_de_passe


# ─────────────────────────── Vie scolaire ───────────────────────────
class IncidentForm(forms.ModelForm):
    """Signalement d'un incident par un surveillant, un professeur ou le censeur."""

    class Meta:
        model = Incident
        fields = ["eleve", "date", "description"]
        labels = {"eleve": "Élève"}
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Ce qui s'est passé, où et quand."}),
        }

    def __init__(self, *args, eleves, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["eleve"].queryset = eleves
        self.fields["eleve"].label_from_instance = lambda e: f"{e.nom} {e.prenom} · {e.classe or 'sans classe'}"
        for champ in self.fields.values():
            champ.widget.attrs.setdefault("class", "form-control")

    def clean_date(self):
        from django.utils import timezone
        date = self.cleaned_data["date"]
        if date > timezone.localdate():
            raise forms.ValidationError("La date ne peut pas être dans le futur.")
        return date


class IncidentTraitementForm(forms.ModelForm):
    """Le censeur décide de la suite : sanction, convocation des parents, clôture."""

    class Meta:
        model = Incident
        fields = ["sanction", "statut", "convocation_le"]
        help_texts = {"convocation_le": "Laissez vide si les parents ne sont pas convoqués."}
        widgets = {
            "sanction": forms.TextInput(attrs={"placeholder": "ex : retenue le samedi, avertissement"}),
            "convocation_le": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # « Signalé » veut dire : pas encore traité. Le censeur passe à « En cours » ou « Clos ».
        self.fields["statut"].choices = [(s, s) for s in choices.STATUTS_INCIDENT if s != choices.INCIDENT_SIGNALE]
        if self.initial.get("statut") == choices.INCIDENT_SIGNALE:
            self.initial["statut"] = choices.INCIDENT_EN_COURS
        for champ in self.fields.values():
            champ.widget.attrs.setdefault("class", "form-control")


# ─────────────────────────── Annonces ───────────────────────────
class AnnonceForm(forms.ModelForm):
    pour = forms.ChoiceField(label="Pour qui ?")

    class Meta:
        model = Annonce
        fields = ["titre", "texte"]
        widgets = {"texte": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields = {"pour": self.fields.pop("pour"), **self.fields}
        options = []
        if roles.portee(user, "annonces", ecriture=True) == "tout":
            options.append(("ecole", "Tous les parents de l'école"))
            sections = Section.objects.all()
            classes = Classe.objects.select_related("section")
        else:
            section = roles.section_de(user)
            sections = Section.objects.filter(pk=section.pk) if section else Section.objects.none()
            classes = Classe.objects.filter(section=section).select_related("section") if section else Classe.objects.none()
        options += [(f"section-{s.pk}", f"Parents de la section {s}") for s in sections]
        for section, liste in par_section(classes):
            options.append((f"Classes{f' · {section}' if section else ''}",
                            [(f"classe-{c.pk}", f"Parents de {c}") for c in liste]))
        self.fields["pour"].choices = options
        if self.instance.pk:
            self.initial["pour"] = (f"classe-{self.instance.classe_id}" if self.instance.classe_id
                                    else f"section-{self.instance.section_id}" if self.instance.section_id else "ecole")
        for champ in self.fields.values():
            champ.widget.attrs.setdefault("class", "form-control")

    def save(self, commit=True):
        genre, _, pk = self.cleaned_data["pour"].partition("-")
        self.instance.section_id = int(pk) if genre == "section" else None
        self.instance.classe_id = int(pk) if genre == "classe" else None
        return super().save(commit)
