# core/context_processors.py
from . import roles


def acces(request):
    """Ce que l'utilisateur connecté peut voir, pour le menu et les boutons."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    from . import parents
    from .views_vie_scolaire import fait_l_appel

    parent = roles.parent_de(user)
    return {
        "acces": {
            module: {"lire": roles.peut(user, module), "ecrire": roles.peut(user, module, ecriture=True)}
            for module in roles.MODULES
        },
        "voit_salaires": roles.voit_salaires(user),
        "utilise_la_gestion": roles.utilise_la_gestion(user),
        "est_professeur": roles.professeur_de(user) is not None,
        "est_parent": parent is not None,
        # Pour le menu du parent : ce qui est nouveau depuis sa dernière visite
        "nouveautes_parent": parents.nouveautes(parent) if parent is not None else None,
        "fait_l_appel": fait_l_appel(user),
    }
