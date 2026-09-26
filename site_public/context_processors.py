# site_public/context_processors.py
from core.telephone import normaliser_telephone

from . import contenu


def site(request):
    """Coordonnées de l'école pour l'en-tête et le bas de chaque page publique."""
    return {
        "site": contenu,
        "whatsapp_lien": f"https://wa.me/{normaliser_telephone(contenu.WHATSAPP)}" if contenu.WHATSAPP else None,
    }
