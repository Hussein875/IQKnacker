"""Erzeugt die einzelnen Video-Frames für ein Rätsel mit Pillow."""

import math
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

EMOJI_RENDER_GROESSE = 109  # Noto Color Emoji ist eine Bitmap-Schrift und gibt es nur in dieser Größe
UNSICHTBAR = {"️", "‍"}


# ---------------------------------------------------------------- Hilfsfunktionen

def hex_zu_rgb(farbe):
    farbe = farbe.lstrip("#")
    return tuple(int(farbe[i:i + 2], 16) for i in (0, 2, 4))


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ist_emoji(zeichen):
    cp = ord(zeichen)
    return cp >= 0x1F000 or 0x2600 <= cp <= 0x27BF or 0x2B00 <= cp <= 0x2BFF or 0x2300 <= cp <= 0x23FF \
        or zeichen in UNSICHTBAR


@lru_cache(maxsize=64)
def schrift(pfad, groesse):
    return ImageFont.truetype(pfad, groesse)


def mit_deckkraft(bild, deckkraft):
    """Gibt eine Kopie des RGBA-Bilds mit reduzierter Deckkraft zurück."""
    if deckkraft >= 0.999:
        return bild
    bild = bild.copy()
    alpha = bild.getchannel("A").point([int(i * deckkraft) for i in range(256)])
    bild.putalpha(alpha)
    return bild


def einfuegen(frame, ebene, mitte, deckkraft=1.0, skalierung=1.0):
    """Setzt eine RGBA-Ebene zentriert auf `mitte` in den Frame."""
    if deckkraft <= 0.001:
        return
    if abs(skalierung - 1.0) > 0.001:
        w = max(1, round(ebene.width * skalierung))
        h = max(1, round(ebene.height * skalierung))
        ebene = ebene.resize((w, h), Image.BICUBIC)
    ebene = mit_deckkraft(ebene, deckkraft)
    x = round(mitte[0] - ebene.width / 2)
    y = round(mitte[1] - ebene.height / 2)
    # Teile außerhalb des Frames abschneiden (alpha_composite erlaubt keine negativen Koordinaten)
    links, oben = max(0, -x), max(0, -y)
    if links or oben:
        ebene = ebene.crop((links, oben, ebene.width, ebene.height))
        x, y = x + links, y + oben
    frame.alpha_composite(ebene, dest=(x, y))


# ---------------------------------------------------------------- Text mit Hervorhebung und Emojis

def zerlege_text(text):
    """Zerlegt Text in Absätze aus Wörtern. *so* markierte Stellen werden in der Akzentfarbe gesetzt.

    Rückgabe: Liste von Absätzen, jeder Absatz ist eine Liste von Wörtern,
    jedes Wort eine Liste von (teiltext, akzent)-Stücken.
    """
    absaetze = []
    akzent = False
    for zeile in text.split("\n"):
        woerter = []
        for roh in zeile.split(" "):
            if roh == "":
                continue
            stuecke, puffer = [], ""
            for z in roh:
                if z == "*":
                    if puffer:
                        stuecke.append((puffer, akzent))
                        puffer = ""
                    akzent = not akzent
                else:
                    puffer += z
            if puffer:
                stuecke.append((puffer, akzent))
            if stuecke:
                woerter.append(stuecke)
        absaetze.append(woerter)
    return absaetze


class TextSetzer:
    def __init__(self, schrift_pfad, emoji_pfad):
        self.schrift_pfad = schrift_pfad
        self.emoji_schrift = None
        if emoji_pfad and os.path.exists(emoji_pfad):
            try:
                self.emoji_schrift = ImageFont.truetype(emoji_pfad, EMOJI_RENDER_GROESSE)
            except OSError:
                self.emoji_schrift = None
        self._emoji_cache = {}

    def _emoji_bild(self, zeichen, hoehe):
        schluessel = (zeichen, hoehe)
        if schluessel not in self._emoji_cache:
            bild = None
            if self.emoji_schrift is not None:
                roh = Image.new("RGBA", (EMOJI_RENDER_GROESSE * 2, EMOJI_RENDER_GROESSE * 2), (0, 0, 0, 0))
                ImageDraw.Draw(roh).text((0, 0), zeichen, font=self.emoji_schrift, embedded_color=True)
                box = roh.getbbox()
                if box:
                    roh = roh.crop(box)
                    breite = max(1, round(roh.width * hoehe / roh.height))
                    bild = roh.resize((breite, hoehe), Image.LANCZOS)
            self._emoji_cache[schluessel] = bild
        return self._emoji_cache[schluessel]

    def _laeufe(self, teiltext):
        """Teilt Text in Läufe aus normalen Zeichen und Emojis."""
        laeufe, puffer, modus = [], "", None
        for z in teiltext:
            m = ist_emoji(z)
            if modus is not None and m != modus:
                laeufe.append((puffer, modus))
                puffer = ""
            puffer += z
            modus = m
        if puffer:
            laeufe.append((puffer, modus))
        return laeufe

    def _emoji_hoehe(self, groesse):
        return round(groesse * 0.95)

    def wortbreite(self, wort, groesse):
        f = schrift(self.schrift_pfad, groesse)
        breite = 0
        for teiltext, _ in wort:
            for lauf, emoji in self._laeufe(teiltext):
                if emoji:
                    for z in lauf:
                        if z in UNSICHTBAR:
                            continue
                        bild = self._emoji_bild(z, self._emoji_hoehe(groesse))
                        breite += (bild.width if bild else 0) + round(groesse * 0.04)
                else:
                    breite += f.getlength(lauf)
        return breite

    def umbrechen(self, text, groesse, max_breite):
        """Gibt Zeilen (Listen von Wörtern) und ob alles in die Breite passt zurück."""
        f = schrift(self.schrift_pfad, groesse)
        leer = f.getlength(" ")
        zeilen, passt = [], True
        for absatz in zerlege_text(text):
            zeile, breite = [], 0
            for wort in absatz:
                wb = self.wortbreite(wort, groesse)
                if wb > max_breite:
                    passt = False
                neue_breite = wb if not zeile else breite + leer + wb
                if zeile and neue_breite > max_breite:
                    zeilen.append(zeile)
                    zeile, breite = [wort], wb
                else:
                    zeile.append(wort)
                    breite = neue_breite
            zeilen.append(zeile)
        return zeilen, passt

    def passende_groesse(self, text, max_breite, max_hoehe, max_groesse, min_groesse, zeilenabstand):
        """Größte Schriftgröße, bei der der Text in den Kasten passt."""
        for groesse in range(max_groesse, min_groesse - 1, -2):
            zeilen, passt = self.umbrechen(text, groesse, max_breite)
            if passt and len(zeilen) * groesse * zeilenabstand <= max_hoehe:
                return groesse
        return min_groesse

    def block(self, text, groesse, max_breite, farbe, akzent, zeilenabstand=1.2):
        """Setzt zentrierten, umbrochenen Text auf eine transparente Ebene."""
        f = schrift(self.schrift_pfad, groesse)
        leer = f.getlength(" ")
        zeilen, _ = self.umbrechen(text, groesse, max_breite)
        zeilenhoehe = round(groesse * zeilenabstand)
        oberlaenge, unterlaenge = f.getmetrics()
        breiten = [sum(self.wortbreite(w, groesse) for w in z) + leer * max(0, len(z) - 1) for z in zeilen]
        ebenen_breite = math.ceil(max(breiten + [1])) + 8
        ebenen_hoehe = zeilenhoehe * (len(zeilen) - 1) + oberlaenge + unterlaenge + 8
        ebene = Image.new("RGBA", (ebenen_breite, ebenen_hoehe), (0, 0, 0, 0))
        zeichnen = ImageDraw.Draw(ebene)
        for i, (zeile, zb) in enumerate(zip(zeilen, breiten)):
            x = (ebenen_breite - zb) / 2
            grundlinie = 4 + oberlaenge + i * zeilenhoehe
            for j, wort in enumerate(zeile):
                if j:
                    x += leer
                for teiltext, ist_akzent in wort:
                    fuellung = akzent if ist_akzent else farbe
                    for lauf, emoji in self._laeufe(teiltext):
                        if emoji:
                            for z in lauf:
                                if z in UNSICHTBAR:
                                    continue
                                bild = self._emoji_bild(z, self._emoji_hoehe(groesse))
                                if bild:
                                    y = round(grundlinie - bild.height * 0.85)
                                    ebene.alpha_composite(bild, dest=(round(x), max(0, y)))
                                    x += bild.width + round(groesse * 0.04)
                        else:
                            zeichnen.text((x, grundlinie), lauf, font=f, fill=fuellung, anchor="ls")
                            x += f.getlength(lauf)
        return ebene


# ---------------------------------------------------------------- Video-Szenen

class RaetselRenderer:
    def __init__(self, config, raetsel, basis_pfad):
        self.cfg = config
        self.raetsel = raetsel
        self.basis = basis_pfad
        v = config["video"]
        self.breite, self.hoehe, self.fps = v["breite"], v["hoehe"], v["fps"]

        farben = config["farben"]
        kat = config["kategorien"].get(raetsel["kategorie"], {})
        self.hintergrund = hex_zu_rgb(farben["hintergrund"]) + (255,)
        self.textfarbe = hex_zu_rgb(farben["text"]) + (255,)
        self.akzent = hex_zu_rgb(kat.get("akzent") or farben["akzent"]) + (255,)
        self.dezent = hex_zu_rgb(farben["dezent"]) + (255,)
        self.label_textfarbe = hex_zu_rgb(farben["label_text"]) + (255,)
        self.balken_hg = hex_zu_rgb(farben["balken_hintergrund"]) + (255,)

        s = config["schriften"]
        self.fett_pfad = self._pfad(s["fett"])
        self.normal_pfad = self._pfad(s.get("normal") or s["fett"])
        emoji_pfad = self._pfad(s["emoji"]) if s.get("emoji") else None
        self.setzer_fett = TextSetzer(self.fett_pfad, emoji_pfad)
        self.setzer_normal = TextSetzer(self.normal_pfad, emoji_pfad)

        z = config["zeiten"]
        self.t_hook = z["hook"]
        self.t_lesen = z["lesezeit"]
        self.t_countdown = z["countdown"]
        self.t_raetsel = z["lesezeit"] + z["countdown"]
        self.t_end = z["endkarte"]
        self.t_uebergang = z["uebergang"]
        self.dauer = self.t_hook + self.t_raetsel + self.t_end

        self._layout()
        self._ebenen_vorbereiten(kat)

    def _pfad(self, p):
        return p if os.path.isabs(p) else os.path.join(self.basis, p)

    @property
    def frame_anzahl(self):
        return round(self.dauer * self.fps)

    # ---- Layout innerhalb der TikTok-Safe-Zones
    def _layout(self):
        sz = self.cfg["safe_zone"]
        self.inhalt_links = sz["links"]
        self.inhalt_rechts = self.breite - sz["rechts"]
        self.inhalt_oben = sz["oben"]
        self.inhalt_unten = self.hoehe - sz["unten"]
        self.inhalt_breite = self.inhalt_rechts - self.inhalt_links
        self.mitte_x = (self.inhalt_links + self.inhalt_rechts) / 2
        hoehe = self.inhalt_unten - self.inhalt_oben

        self.label_y = self.inhalt_oben + 0.08 * hoehe
        self.text_oben = self.inhalt_oben + 0.17 * hoehe
        self.text_unten = self.inhalt_oben + 0.74 * hoehe
        self.countdown_y = self.inhalt_oben + 0.83 * hoehe
        self.balken_y = self.inhalt_oben + 0.955 * hoehe
        self.mitte_y = (self.inhalt_oben + self.inhalt_unten) / 2

    def _ebenen_vorbereiten(self, kat):
        g = self.cfg["groessen"]
        texte = self.cfg["texte"]
        textbreite = self.inhalt_breite - 20

        # Hook
        self.hook_ebene = self.setzer_fett.block(texte["hook"], g["hook"], textbreite, self.textfarbe,
                                                 self.akzent, 1.1)
        groesse = g["hook"]
        while self.hook_ebene.width > textbreite and groesse > 40:
            groesse -= 4
            self.hook_ebene = self.setzer_fett.block(texte["hook"], groesse, textbreite, self.textfarbe,
                                                     self.akzent, 1.1)

        # Kategorie-Label als gefüllte Pille
        label_text = kat.get("label") or self.raetsel["kategorie"].upper()
        f = schrift(self.fett_pfad, g["label"])
        box = f.getbbox(label_text, anchor="ls")
        pad_x, pad_y = round(g["label"] * 0.7), round(g["label"] * 0.45)
        w = (box[2] - box[0]) + 2 * pad_x
        h = (box[3] - box[1]) + 2 * pad_y
        self.label_ebene = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(self.label_ebene)
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=self.akzent)
        d.text((pad_x - box[0], pad_y - box[1]), label_text, font=f, fill=self.label_textfarbe, anchor="ls")

        # Rätseltext (optional mit Bild darüber, z. B. für die Kategorie "bild")
        kasten_hoehe = self.text_unten - self.text_oben
        self.bild_ebene = None
        bild_pfad = self.raetsel.get("bild")
        if bild_pfad:
            pfad = self._pfad(bild_pfad)
            if not os.path.exists(pfad):
                raise FileNotFoundError(f"Bild für Rätsel {self.raetsel['id']} nicht gefunden: {pfad}")
            bild = Image.open(pfad).convert("RGBA")
            max_b, max_h = textbreite, kasten_hoehe * 0.55
            faktor = min(max_b / bild.width, max_h / bild.height)
            self.bild_ebene = bild.resize((round(bild.width * faktor), round(bild.height * faktor)), Image.LANCZOS)
            kasten_hoehe -= self.bild_ebene.height + 40

        groesse = self.setzer_fett.passende_groesse(self.raetsel["frage"], textbreite, kasten_hoehe,
                                                    g["raetsel_max"], g["raetsel_min"], g["zeilenabstand"])
        self.raetsel_schriftgroesse = groesse
        self.text_ebene = self.setzer_fett.block(self.raetsel["frage"], groesse, textbreite, self.textfarbe,
                                                 self.akzent, g["zeilenabstand"])
        if self.bild_ebene is not None:
            # Bild und Text zu einer Ebene zusammenfassen, damit beide gemeinsam animiert werden
            abstand = 40
            w = max(self.bild_ebene.width, self.text_ebene.width)
            h = self.bild_ebene.height + abstand + self.text_ebene.height
            kombi = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            kombi.alpha_composite(self.bild_ebene, ((w - self.bild_ebene.width) // 2, 0))
            kombi.alpha_composite(self.text_ebene, ((w - self.text_ebene.width) // 2,
                                                    self.bild_ebene.height + abstand))
            self.text_ebene = kombi

        # Countdown-Zahlen 5 ... 1
        self.zahl_ebenen = {}
        for n in range(1, math.ceil(self.t_countdown) + 1):
            self.zahl_ebenen[n] = self.setzer_fett.block(str(n), g["countdown_zahl"], 400, self.akzent,
                                                         self.akzent, 1.0)

        # Endkarte
        self.end1_ebene = self.setzer_fett.block(texte["endkarte_1"], g["endkarte_1"], textbreite,
                                                 self.textfarbe, self.akzent, 1.2)
        self.end2_ebene = self.setzer_fett.block(texte["endkarte_2"], g["endkarte_2"], textbreite,
                                                 self.akzent, self.textfarbe, 1.2)
        self.handle_ebene = self.setzer_normal.block(texte.get("handle", ""), g["handle"], textbreite,
                                                     self.dezent, self.akzent, 1.2) if texte.get("handle") else None

        self._wasserzeichen_vorbereiten()

    def _wasserzeichen_vorbereiten(self):
        wz = self.cfg["wasserzeichen"]
        ebene = None
        if wz.get("datei"):
            pfad = self._pfad(wz["datei"])
            if os.path.exists(pfad):
                logo = Image.open(pfad).convert("RGBA")
                box = logo.getbbox()
                if box:
                    logo = logo.crop(box)
                h = wz["hoehe"]
                ebene = logo.resize((max(1, round(logo.width * h / logo.height)), h), Image.LANCZOS)
        if ebene is None and wz.get("text_falls_kein_logo"):
            ebene = self.setzer_normal.block(wz["text_falls_kein_logo"], self.cfg["groessen"]["wasserzeichen_text"],
                                             600, self.textfarbe, self.akzent, 1.0)
        if ebene is None:
            self.wasserzeichen = None
            return
        ebene = mit_deckkraft(ebene, wz.get("deckkraft", 0.6))
        rand = 20
        pos = wz.get("position", "oben_links")
        x = self.inhalt_links if "links" in pos else self.inhalt_rechts - ebene.width
        y = self.inhalt_oben + rand if "oben" in pos else self.inhalt_unten - rand - ebene.height
        self.wasserzeichen = (ebene, (round(x), round(y)))

    # ---- Frame-Erzeugung
    def frame(self, t):
        bild = Image.new("RGBA", (self.breite, self.hoehe), self.hintergrund)
        if t < self.t_hook:
            self._szene_hook(bild, t)
        elif t < self.t_hook + self.t_raetsel:
            self._szene_raetsel(bild, t - self.t_hook)
        else:
            self._szene_ende(bild, t - self.t_hook - self.t_raetsel)
        if self.wasserzeichen:
            ebene, pos = self.wasserzeichen
            bild.alpha_composite(ebene, dest=pos)
        return bild.convert("RGB")

    def _ausblenden(self, t, dauer):
        """Faktor für das Ausblenden am Ende einer Szene."""
        if self.t_uebergang <= 0:
            return 1.0
        return clamp((dauer - t) / self.t_uebergang)

    def _szene_hook(self, bild, t):
        a = self.cfg["animation"]
        p = ease_out(t / max(0.01, a["einblenden_dauer"] + 0.2))
        deckkraft = p * self._ausblenden(t, self.t_hook)
        skalierung = 0.85 + 0.15 * p
        einfuegen(bild, self.hook_ebene, (self.mitte_x, self.mitte_y), deckkraft, skalierung)

    def _szene_raetsel(self, bild, t):
        a = self.cfg["animation"]
        dauer_ein = max(0.01, a["einblenden_dauer"])
        raus = self._ausblenden(t, self.t_raetsel)

        # Label
        p_label = ease_out(t / dauer_ein)
        einfuegen(bild, self.label_ebene, (self.mitte_x, self.label_y + 20 * (1 - p_label)), p_label * raus)

        # Rätseltext: Einblenden mit leichtem Zoom, danach ganz langsames Heranzoomen
        p_text = ease_out((t - 0.1) / dauer_ein)
        zoom = a["zoom_start"] + (1 - a["zoom_start"]) * p_text
        zoom *= 1 + a["zoom_drift"] * (t / self.t_raetsel)
        text_mitte_y = (self.text_oben + self.text_unten) / 2
        einfuegen(bild, self.text_ebene, (self.mitte_x, text_mitte_y), p_text * raus, zoom)

        # Countdown
        c = t - self.t_lesen
        if c < -0.3:
            return
        stil = self.cfg["countdown"].get("stil", "beides")
        p_cd = ease_out((c + 0.3) / 0.4) * raus
        rest = clamp(1 - c / self.t_countdown)

        if stil in ("zahlen", "beides"):
            n = int(clamp(self.t_countdown - math.floor(max(c, 0)), 1, self.t_countdown))
            in_sekunde = max(c, 0) - math.floor(max(c, 0))
            puls = 1 + a["countdown_puls"] * (1 - ease_out(in_sekunde / 0.3))
            ebene = self.zahl_ebenen.get(n)
            if ebene is not None:
                einfuegen(bild, ebene, (self.mitte_x, self.countdown_y), p_cd, puls)

        if stil in ("balken", "beides"):
            g = self.cfg["groessen"]
            bb, bh = g["countdown_balken_breite"], g["countdown_balken_hoehe"]
            balken = Image.new("RGBA", (bb, bh), (0, 0, 0, 0))
            d = ImageDraw.Draw(balken)
            d.rounded_rectangle((0, 0, bb - 1, bh - 1), radius=bh // 2, fill=self.balken_hg)
            fuell = round(bb * rest)
            if fuell >= bh:
                d.rounded_rectangle((0, 0, fuell - 1, bh - 1), radius=bh // 2, fill=self.akzent)
            einfuegen(bild, balken, (self.mitte_x, self.balken_y), p_cd)

    def _szene_ende(self, bild, t):
        a = self.cfg["animation"]
        dauer_ein = max(0.01, a["einblenden_dauer"])
        p1 = ease_out(t / dauer_ein)
        p2 = ease_out((t - 0.3) / dauer_ein)
        p3 = ease_out((t - 0.5) / dauer_ein)
        abstand = 70
        h1, h2 = self.end1_ebene.height, self.end2_ebene.height
        h3 = self.handle_ebene.height if self.handle_ebene else 0
        gesamt = h1 + abstand + h2 + (abstand * 0.6 + h3 if h3 else 0)
        y = self.mitte_y - gesamt / 2
        einfuegen(bild, self.end1_ebene, (self.mitte_x, y + h1 / 2 + 15 * (1 - p1)), p1, 0.96 + 0.04 * p1)
        y += h1 + abstand
        einfuegen(bild, self.end2_ebene, (self.mitte_x, y + h2 / 2 + 15 * (1 - p2)), p2, 0.96 + 0.04 * p2)
        if self.handle_ebene:
            y += h2 + abstand * 0.6
            einfuegen(bild, self.handle_ebene, (self.mitte_x, y + h3 / 2), p3)

    def vorschau_zeitpunkt(self):
        """Zeitpunkt für das Vorschaubild: Rätsel vollständig sichtbar, Countdown bei 5."""
        return self.t_hook + self.t_lesen + 0.35
