# core/bulletins_fichiers.py
# Bulletins à télécharger : un PDF (une page par élève, pour imprimer ou envoyer)
# et une image PNG (pratique à partager par WhatsApp). Le PNG est la première
# page du PDF, pour que les deux soient toujours identiques.
from io import BytesIO

import pypdfium2
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image, ImageChops
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from . import choices

BLEU = colors.HexColor("#1e3a8a")
VIOLET = colors.HexColor("#7c3aed")
GRIS = colors.HexColor("#64748b")
FOND = colors.HexColor("#f1f5f9")
LIGNE = colors.HexColor("#e2e8f0")
ORANGE = colors.HexColor("#b45309")

TEXTE = ParagraphStyle("texte", fontName="Helvetica", fontSize=10, leading=13)
PETIT = ParagraphStyle("petit", parent=TEXTE, fontSize=8, leading=10, textColor=GRIS)
GRAS = ParagraphStyle("gras", parent=TEXTE, fontName="Helvetica-Bold")
CASE_TITRE = ParagraphStyle("case-titre", parent=PETIT, alignment=TA_CENTER)
CASE_VALEUR = ParagraphStyle("case-valeur", parent=TEXTE, fontName="Helvetica-Bold", fontSize=13, leading=16,
                             alignment=TA_CENTER, textColor=BLEU)


def _note(valeur):
    """Comme le filtre « note » des pages : 80, 72,5, 72,25."""
    if valeur is None:
        return "—"
    return f"{valeur.normalize():f}".replace(".", ",")


def _rang(fiche):
    if not fiche["rang"]:
        return "—"
    return f"{fiche['rang']}{'er' if fiche['rang'] == 1 else 'e'} sur {fiche['effectif']}"


def _p(texte, style=TEXTE):
    return Paragraph(escape(str(texte)), style)


def _entete(periode, annee):
    def dessiner(canvas, doc):
        largeur, hauteur = A4
        canvas.saveState()
        canvas.setFillColor(BLEU)
        canvas.rect(0, hauteur - 32 * mm, largeur, 32 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 19)
        canvas.drawString(18 * mm, hauteur - 15 * mm, choices.NOM_ECOLE)
        canvas.setFont("Helvetica", 10)
        canvas.drawString(18 * mm, hauteur - 22 * mm, f"{choices.VILLE_ECOLE}, Haïti · Année scolaire {annee}")
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(largeur - 18 * mm, hauteur - 14 * mm, "BULLETIN")
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawRightString(largeur - 18 * mm, hauteur - 21 * mm, periode.upper())
        canvas.restoreState()
    return dessiner


def _brouillon(canvas, doc):
    """Filigrane « APERÇU » sur un bulletin qui n'est pas encore validé."""
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#fde68a"))
    canvas.setFont("Helvetica-Bold", 90)
    canvas.translate(A4[0] / 2, A4[1] / 2)
    canvas.rotate(35)
    canvas.drawCentredString(0, 0, "APERÇU")
    canvas.restoreState()


def _page(fiche):
    """Les éléments d'une page de bulletin, comme sur l'écran (core/_bulletin.html)."""
    eleve, classe, bulletin = fiche["eleve"], fiche["classe"], fiche["bulletin"]
    classe_texte = str(classe) if classe else "—"
    if classe is not None and classe.section_id:
        classe_texte += f" · {classe.section}"
    elements = [Table([
        [_p("Élève", PETIT), _p(f"{eleve.nom.upper()} {eleve.prenom}", GRAS)],
        [_p("Classe", PETIT), _p(classe_texte, GRAS)],
    ], colWidths=[22 * mm, None], style=[("LEFTPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]),
        Spacer(1, 5 * mm)]

    lignes = [[_p("MATIÈRE", PETIT), _p("NOTE SUR 100", CASE_TITRE), _p("MOYENNE DE LA CLASSE", CASE_TITRE)]]
    for ligne in fiche["lignes"]:
        matiere = [_p(ligne["matiere"])]
        if ligne.get("professeur"):
            matiere.append(_p(ligne["professeur"], PETIT))
        lignes.append([matiere, _p(_note(ligne["note"]), ParagraphStyle("n", parent=GRAS, alignment=TA_CENTER)),
                       _p(_note(ligne["moyenne_classe"]), ParagraphStyle("m", parent=TEXTE, alignment=TA_CENTER))])
    if len(lignes) == 1:
        lignes.append([_p("Pas de notes pour ce trimestre."), "", ""])
    tableau = Table(lignes, colWidths=[90 * mm, 40 * mm, 44 * mm], repeatRows=1)
    tableau.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LIGNE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ] + [("BACKGROUND", (0, i), (-1, i), FOND) for i in range(2, len(lignes), 2)]))
    elements += [tableau, Spacer(1, 6 * mm)]

    cases = [("Moyenne générale", f"{_note(fiche['moyenne'])} / 100" if fiche["moyenne"] is not None else "—"),
             ("Rang", _rang(fiche)), ("Absences", fiche["absences"]), ("Retards", fiche["retards"]),
             ("Conduite", (bulletin.conduite if bulletin else "") or "—")]
    resultats = Table([[[_p(titre, CASE_TITRE), _p(valeur, CASE_VALEUR)] for titre, valeur in cases]],
                      colWidths=[174 * mm / 5] * 5)
    resultats.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), FOND), ("LINEAFTER", (0, 0), (-2, -1), 3, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements += [resultats, Spacer(1, 6 * mm)]

    if bulletin is not None and bulletin.appreciation:
        appreciation = Paragraph(f"<b>Appréciation :</b> {escape(bulletin.appreciation)}", TEXTE)
        elements += [Table([[appreciation]], colWidths=[174 * mm], style=[
            ("LINEBEFORE", (0, 0), (0, -1), 3, VIOLET), ("LEFTPADDING", (0, 0), (-1, -1), 8)]), Spacer(1, 5 * mm)]

    if bulletin is not None and bulletin.valide:
        par = ""
        if bulletin.valide_par:
            par = f" ({bulletin.valide_par.get_full_name() or bulletin.valide_par.username})"
        date = timezone.localtime(bulletin.valide_le).strftime("%d/%m/%Y") if bulletin.valide_le else ""
        pied = _p(f"Validé par la direction{par} le {date}.", PETIT)
    else:
        pied = _p("Aperçu : ce bulletin n'est pas encore validé, les parents ne le voient pas.",
                  ParagraphStyle("b", parent=PETIT, textColor=ORANGE))
    signatures = Table([["", "", ""], [_p("La direction", CASE_TITRE), "", _p("Les parents", CASE_TITRE)]],
                       colWidths=[55 * mm, 64 * mm, 55 * mm], rowHeights=[18 * mm, None])
    signatures.setStyle(TableStyle([("LINEBELOW", (0, 0), (0, 0), 0.7, GRIS), ("LINEBELOW", (2, 0), (2, 0), 0.7, GRIS)]))
    elements += [pied, Spacer(1, 4 * mm), KeepTogether(signatures)]
    return elements


def pdf(fiches, periode, annee):
    """Le PDF des bulletins : une page par élève."""
    tampon = BytesIO()
    document = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                                 topMargin=42 * mm, bottomMargin=16 * mm,
                                 title=f"Bulletins · {periode} · {annee}", author=choices.NOM_ECOLE)
    elements = []
    for i, fiche in enumerate(fiches):
        if i:
            elements.append(PageBreak())
        elements += _page(fiche)
    entete = _entete(periode, annee)
    brouillon = any(not (f["bulletin"] and f["bulletin"].valide) for f in fiches)

    def sur_chaque_page(canvas, doc):
        if brouillon:
            _brouillon(canvas, doc)
        entete(canvas, doc)
    document.build(elements, onFirstPage=sur_chaque_page, onLaterPages=sur_chaque_page)
    return tampon.getvalue()


def png(fiche, periode, annee):
    """L'image PNG du bulletin d'un élève (sa page du PDF, en bonne résolution)."""
    document = pypdfium2.PdfDocument(pdf([fiche], periode, annee))
    try:
        image = document[0].render(scale=2).to_pil().convert("RGB")
    finally:
        document.close()
    # On coupe le blanc sous les signatures : l'image se lit mieux sur un téléphone
    boite = ImageChops.difference(image, Image.new("RGB", image.size, "white")).getbbox()
    if boite:
        image = image.crop((0, 0, image.width, min(image.height, boite[3] + 80)))
    tampon = BytesIO()
    image.save(tampon, "PNG", optimize=True)
    return tampon.getvalue()


def nom_de_fichier(periode, annee, extension, eleve=None, classe=None):
    """« bulletin-martin-marie-1er-trimestre-2026-2027.pdf » ou « bulletins-8eme-af-… »."""
    qui = f"bulletin-{eleve.nom}-{eleve.prenom}" if eleve is not None else f"bulletins-{classe}"
    return f"{slugify(f'{qui} {periode} {annee}')}.{extension}"
