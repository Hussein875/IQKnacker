"""Gezeichnete Figuren für „Wer hat recht?“: Anna und Ben als Brustbild mit wechselnder Miene.

Das Aussehen steht in config.json unter `figuren` (Haut, Haare, Frisur, Shirt, Brille, Teamfarbe).
Stimmungen: sicher (vor der Auflösung), freut (hatte recht), geschockt (lag falsch).
Alles mit Pillow gezeichnet – gleicher Stil in jedem Video, keine fremden Bilder.
"""

from PIL import Image, ImageDraw

S = 2             # doppelt zeichnen und verkleinern = glatte Kanten
BREITE, HOEHE = 300, 330
STANDARD = {
    "links": {"haut": "#F2C9A0", "haare": "#7A3E1D", "frisur": "lang", "shirt": "#FF7EB6", "farbe": "#FF7EB6"},
    "rechts": {"haut": "#E0A878", "haare": "#23232B", "frisur": "kurz", "shirt": "#56CCF2", "farbe": "#56CCF2",
               "brille": True},
}


def rgb(farbe):
    farbe = farbe.lstrip("#")
    return tuple(int(farbe[i:i + 2], 16) for i in (0, 2, 4))


def dunkler(farbe, faktor=0.82):
    return tuple(int(c * faktor) for c in farbe)


def aussehen(cfg, name, seite):
    """Aussehen einer Figur: Eintrag aus config.json (`figuren.<name>`), sonst das Standard-Aussehen der Seite."""
    return {**STANDARD[seite], **cfg.get("figuren", {}).get(str(name).lower(), {})}


def brustbild(f, stimmung="sicher", groesse=1.0):
    """Kopf und Schultern als RGBA-Bild (Unterkante = Bildunterkante)."""
    bild = Image.new("RGBA", (BREITE * S, HOEHE * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(bild)
    haut, haare, shirt = rgb(f["haut"]), rgb(f["haare"]), rgb(f["shirt"])
    dunkel = (34, 30, 36)
    mx, ky, r = 150, 138, 96

    def oval(x, y, rx, ry, **kw):
        d.ellipse(((x - rx) * S, (y - ry) * S, (x + rx) * S, (y + ry) * S), **kw)

    def linie(punkte, farbe, breite):
        d.line([(x * S, y * S) for x, y in punkte], fill=farbe, width=round(breite * S), joint="curve")
        for x, y in (punkte[0], punkte[-1]):
            oval(x, y, breite / 2, breite / 2, fill=farbe)

    if f.get("frisur") == "lang":                                # Haare hinter Kopf und Schultern
        d.rounded_rectangle(((mx - 112) * S, (ky - 60) * S, (mx + 112) * S, (ky + 170) * S), 80 * S, fill=haare)
    oval(mx, 372, 142, 122, fill=shirt)                          # Schultern
    oval(mx, 262, 46, 22, fill=dunkler(shirt, 0.88))             # Ausschnitt
    d.rectangle(((mx - 27) * S, (ky + 78) * S, (mx + 27) * S, 258 * S), fill=dunkler(haut, 0.9))
    oval(mx, ky, r, r, fill=haut)
    for seite in (-1, 1):                                        # Ohren
        oval(mx + seite * (r - 2), ky + 8, 14, 20, fill=dunkler(haut, 0.93))
    if f.get("frisur") == "lang":
        d.chord(((mx - r - 6) * S, (ky - r - 10) * S, (mx + r + 6) * S, (ky + r - 36) * S), 180, 360, fill=haare)
        d.polygon([((mx - r - 6) * S, (ky - 34) * S), ((mx - 20) * S, (ky - r + 4) * S), ((mx - 52) * S, (ky - 8) * S),
                   ((mx - r - 6) * S, (ky + 40) * S)], fill=haare)
        d.polygon([((mx + r + 6) * S, (ky - 34) * S), ((mx + 30) * S, (ky - r + 4) * S), ((mx + 70) * S, (ky - 4) * S),
                   ((mx + r + 6) * S, (ky + 40) * S)], fill=haare)
    else:
        d.chord(((mx - r - 5) * S, (ky - r - 12) * S, (mx + r + 5) * S, (ky + r - 44) * S), 180, 360, fill=haare)
        d.polygon([((mx - r + 12) * S, (ky - 30) * S), ((mx - 56) * S, (ky - r + 20) * S), ((mx + 44) * S, (ky - r + 8) * S),
                   ((mx + r - 12) * S, (ky - 30) * S), ((mx + r - 8) * S, (ky - 58) * S), ((mx - r + 8) * S, (ky - 58) * S)],
                  fill=haare)

    augen_y = ky + 8
    for seite in (-1, 1):
        ax = mx + seite * 37
        if stimmung == "freut":                                  # lachende Augen
            d.arc(((ax - 17) * S, (augen_y - 12) * S, (ax + 17) * S, (augen_y + 22) * S), 205, 335, fill=dunkel,
                  width=7 * S)
        elif stimmung == "geschockt":
            oval(ax, augen_y, 19, 23, fill=(255, 255, 255))
            oval(ax, augen_y + 2, 8, 9, fill=dunkel)
        else:
            oval(ax, augen_y, 12, 14, fill=dunkel)
            oval(ax - 3, augen_y - 5, 4, 4, fill=(255, 255, 255))
        hoch = augen_y - {"geschockt": 44, "freut": 34}.get(stimmung, 33)
        kipp = {"sicher": -2, "geschockt": 5}.get(stimmung, 0) * seite
        linie([(ax - 17, hoch - kipp), (ax + 17, hoch + kipp)], dunkler(haare, 0.7), 7)
    if f.get("brille"):
        for seite in (-1, 1):
            d.ellipse(((mx + seite * 37 - 29) * S, (augen_y - 27) * S, (mx + seite * 37 + 29) * S, (augen_y + 27) * S),
                      outline=dunkel, width=6 * S)
        linie([(mx - 9, augen_y), (mx + 9, augen_y)], dunkel, 6)
    mund_y = ky + 56
    if stimmung == "freut":
        d.chord(((mx - 38) * S, (mund_y - 30) * S, (mx + 38) * S, (mund_y + 24) * S), 0, 180, fill=(150, 40, 52))
        for seite in (-1, 1):
            oval(mx + seite * 66, ky + 42, 16, 9, fill=(245, 150, 150))
    elif stimmung == "geschockt":
        oval(mx, mund_y + 4, 15, 19, fill=(112, 32, 42))
    else:                                                        # selbstsicheres Lächeln, leicht schief
        d.arc(((mx - 30) * S, (mund_y - 26) * S, (mx + 36) * S, (mund_y + 10) * S), 15, 150, fill=(96, 44, 44),
              width=7 * S)
    return bild.resize((round(BREITE * groesse), round(HOEHE * groesse)), Image.LANCZOS)
