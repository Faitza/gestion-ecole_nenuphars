# plateforme/routeur.py
# Envoie chaque requête à la base de l'école en cours (voir plateforme/ecoles.py).
# Le registre des écoles (app « plateforme ») reste toujours dans la base « default ».
from . import ecoles


class RouteurEcoles:
    def db_for_read(self, model, **hints):
        if model._meta.app_label == "plateforme":
            return "default"
        return ecoles.alias()

    db_for_write = db_for_read

    def allow_relation(self, obj1, obj2, **hints):
        # Jamais de lien entre deux bases différentes
        return obj1._state.db == obj2._state.db

    def allow_migrate(self, db, app_label, **hints):
        if app_label == "plateforme":
            return db == "default"
        return True
