# core/pagination.py
# Les longues listes sont montrées par pages : la page arrive vite, même sur un
# téléphone avec une connexion lente, et la base ne lit que les lignes affichées.
from django.core.paginator import Paginator

PAR_PAGE = 50


def paginer(request, liste, par_page=PAR_PAGE):
    """La page demandée (?page=N) ; une page trop grande ou mal écrite donne la dernière ou la première."""
    page = Paginator(liste, par_page).get_page(request.GET.get("page"))
    # Les autres filtres de l'adresse (recherche, onglet...) sont gardés d'une page à l'autre
    parametres = request.GET.copy()
    parametres.pop("page", None)
    page.parametres = parametres.urlencode()
    page.numeros = list(page.paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1))
    return page
