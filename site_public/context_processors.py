from core.telephone import normaliser_telephone

from . import contenu


def site(request):
    """Coordonnées de l'école pour l'en-tête et le bas de chaque page publique."""
    textes = contenu.du_site()
    return {
        "site": textes,
        "whatsapp_lien": f"https://wa.me/{normaliser_telephone(textes.WHATSAPP)}" if textes.WHATSAPP else None,
    }
