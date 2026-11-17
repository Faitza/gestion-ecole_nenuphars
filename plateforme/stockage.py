# plateforme/stockage.py
# Les photos et pièces jointes de chaque école sont dans leur propre dossier :
# MEDIA_ROOT/ecoles/<adresse>/... ; sans école active (une seule école), MEDIA_ROOT comme avant.
import os
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage

from . import ecoles


class StockageParEcole(FileSystemStorage):
    @property
    def base_location(self):
        ecole = ecoles.active()
        racine = Path(self._value_or_setting(self._location, settings.MEDIA_ROOT))
        return str(racine / "ecoles" / ecole.code) if ecole is not None else str(racine)

    @property
    def location(self):
        return os.path.abspath(self.base_location)
