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


def ease_out_back(x):
    """Schießt leicht über das Ziel hinaus und federt zurück – für „Pop“-Effekte."""
    x = clamp(x)
    c1 = 1.70158
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def farbmix(a, b, anteil):
    return tuple(round(x + (y - x) * anteil) for x, y in zip(a, b))


def radialer_verlauf(breite, hoehe, farbe, innen, aussen, staerke=1.0):
    """Ebene mit radialem Verlauf von Deckkraft `innen` (Mitte) zu `aussen` (Rand)."""
    klein_b, klein_h = max(8, breite // 10), max(8, hoehe // 10)
    alpha = Image.new("L", (klein_b, klein_h))
    pixel = alpha.load()
    for y in range(klein_h):
        for x in range(klein_b):
            dx = (x + 0.5) / klein_b * 2 - 1
            dy = (y + 0.5) / klein_h * 2 - 1
            d = clamp(math.hypot(dx, dy) / math.sqrt(2) * 1.25)
            pixel[x, y] = round(255 * (innen + (aussen - innen) * d ** staerke))
    ebene = Image.new("RGBA", (breite, hoehe), farbe[:3] + (0,))
    ebene.putalpha(alpha.resize((breite, hoehe), Image.BICUBIC))
    return ebene


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

    def block_mit_woertern(self, text, groesse, max_breite, farbe, akzent, zeilenabstand=1.2):
        """Setzt zentrierten, umbrochenen Text auf eine transparente Ebene.

        Rückgabe: (Ebene, Liste der Wort-Rechtecke) – die Rechtecke braucht die Wort-für-Wort-Animation.
        """
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
        wortboxen = []

        def zeilengrenze(i):
            unterkante_davor = 4 + oberlaenge + (i - 1) * zeilenhoehe + unterlaenge
            oberkante = 4 + i * zeilenhoehe
            return round((unterkante_davor + oberkante) / 2)

        for i, (zeile, zb) in enumerate(zip(zeilen, breiten)):
            x = (ebenen_breite - zb) / 2
            grundlinie = 4 + oberlaenge + i * zeilenhoehe
            for j, wort in enumerate(zeile):
                if j:
                    x += leer
                wort_start = x
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
                # Rechtecke überlappen sich nicht: Grenzen liegen mittig zwischen Wörtern bzw. Zeilen
                oben = 0 if i == 0 else zeilengrenze(i)
                unten = ebenen_hoehe if i == len(zeilen) - 1 else zeilengrenze(i + 1)
                wortboxen.append((max(0, math.floor(wort_start - leer / 2)), oben,
                                  min(ebenen_breite, math.ceil(x + leer / 2)), unten))
        return ebene, wortboxen

    def block(self, *args, **kwargs):
        """Wie block_mit_woertern, aber nur die fertige Ebene."""
        return self.block_mit_woertern(*args, **kwargs)[0]


# ---------------------------------------------------------------- Video-Szenen

class RaetselRenderer:
    """Ablauf: Hook → Rätsel (Wort für Wort, dann Countdown) → „Zeit um!“ → Endkarte."""

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
        self.warnung = hex_zu_rgb(farben.get("warnung", "#FF4D4D")) + (255,)
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
        self.t_zeit_um = z.get("zeit_um", 0)
        self.t_end = z["endkarte"]
        self.t_uebergang = z["uebergang"]
        self.dauer = self.t_hook + self.t_raetsel + self.t_zeit_um + self.t_end

        a = config["animation"]
        self.kritisch_ab = a.get("kritisch_ab", 3)
        self.wort_intervall = a.get("wort_intervall", 0.12)
        self.wort_dauer = a.get("wort_einblenden", 0.25)

        self._layout()
        self._ebenen_vorbereiten(kat)

    def _pfad(self, p):
        return p if os.path.isabs(p) else os.path.join(self.basis, p)

    @property
    def frame_anzahl(self):
        return round(self.dauer * self.fps)

    # ---- Zeitpunkte für Soundeffekte (in Sekunden ab Videostart)
    def ticks(self):
        """Liste (zeit, kritisch) – ein Tick pro Countdown-Sekunde."""
        start = self.t_hook + self.t_lesen
        n = math.ceil(self.t_countdown)
        return [(start + i, n - i <= self.kritisch_ab) for i in range(n)]

    def zeit_um_zeitpunkt(self):
        return self.t_hook + self.t_raetsel

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

        g = self.cfg["groessen"]
        self.ring_d = g.get("countdown_ring_durchmesser", 280)
        self.label_y = self.inhalt_oben + 0.08 * hoehe
        self.text_oben = self.inhalt_oben + 0.15 * hoehe
        self.countdown_y = self.inhalt_unten - self.ring_d / 2 - 30
        self.text_unten = self.countdown_y - self.ring_d / 2 - 40
        self.balken_y = self.countdown_y + self.ring_d / 2 - 10
        self.mitte_y = (self.inhalt_oben + self.inhalt_unten) / 2

    def _ebenen_vorbereiten(self, kat):
        g = self.cfg["groessen"]
        texte = self.cfg["texte"]
        a = self.cfg["animation"]
        textbreite = self.inhalt_breite - 20

        # Hook + Unterzeile passend zur Schwierigkeit
        groesse = g["hook"]
        while True:
            self.hook_ebene, self.hook_boxen = self.setzer_fett.block_mit_woertern(
                texte["hook"], groesse, textbreite, self.textfarbe, self.akzent, 1.1)
            if self.hook_ebene.width <= textbreite + 8 or groesse <= 40:
                break
            groesse -= 4
        unterzeilen = texte.get("hook_unterzeile", {})
        unterzeile = unterzeilen.get(str(self.raetsel.get("schwierigkeit", "")).lower()) \
            if isinstance(unterzeilen, dict) else unterzeilen
        self.hook_unter_ebene = None
        if unterzeile:
            groesse = g.get("hook_unterzeile", 46)
            while groesse > 28 and len(self.setzer_fett.umbrechen(unterzeile, groesse, textbreite)[0]) > 1:
                groesse -= 2  # Unterzeile soll einzeilig bleiben
            self.hook_unter_ebene = self.setzer_fett.block(unterzeile, groesse, textbreite, self.akzent,
                                                           self.textfarbe, 1.2)

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
        self.text_ebene, self.text_boxen = self.setzer_fett.block_mit_woertern(
            self.raetsel["frage"], groesse, textbreite, self.textfarbe, self.akzent, g["zeilenabstand"])
        self.bild_versatz = 0
        if self.bild_ebene is not None:
            self.bild_versatz = self.bild_ebene.height + 40

        # Wort-Animation so takten, dass der Text vor dem Countdown komplett steht
        n = max(1, len(self.text_boxen))
        self.text_intervall = min(self.wort_intervall, max(0.02, (self.t_lesen - 0.3 - self.wort_dauer) / n))

        # Countdown-Zahlen in Normal- und Warnfarbe
        self.zahl_ebenen = {}
        for n in range(1, math.ceil(self.t_countdown) + 1):
            for farbe in (self.akzent, self.warnung):
                self.zahl_ebenen[(n, farbe)] = self.setzer_fett.block(str(n), g["countdown_zahl"], 400, farbe,
                                                                      farbe, 1.0)

        # „Zeit um!“
        self.zeit_um_ebene = None
        if self.t_zeit_um > 0 and texte.get("zeit_um"):
            self.zeit_um_ebene = self.setzer_fett.block(texte["zeit_um"], g.get("zeit_um", 130), textbreite,
                                                        self.warnung, self.textfarbe, 1.1)

        # Endkarte
        self.end1_ebene = self.setzer_fett.block(texte["endkarte_1"], g["endkarte_1"], textbreite,
                                                 self.textfarbe, self.akzent, 1.2)
        self.end2_ebene = self.setzer_fett.block(texte["endkarte_2"], g["endkarte_2"], textbreite,
                                                 self.akzent, self.textfarbe, 1.2)
        self.handle_ebene = self.setzer_normal.block(texte.get("handle", ""), g["handle"], textbreite,
                                                     self.dezent, self.akzent, 1.2) if texte.get("handle") else None

        # Hintergrund-Effekte: weiches Leuchten hinter dem Text und roter Rand für die letzten Sekunden
        self.glow_ebene = None
        if a.get("glow_deckkraft", 0) > 0:
            d = round(self.inhalt_breite * 1.25)
            self.glow_ebene = radialer_verlauf(d, d, self.akzent, a["glow_deckkraft"], 0.0, 1.4)
        self.vignette = None
        if a.get("vignette_deckkraft", 0) > 0:
            self.vignette = radialer_verlauf(self.breite, self.hoehe, self.warnung, 0.0, a["vignette_deckkraft"], 2.2)

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
        ende_raetsel = self.t_hook + self.t_raetsel
        if t < self.t_hook:
            self._szene_hook(bild, t)
        elif t < ende_raetsel:
            self._szene_raetsel(bild, t - self.t_hook)
        elif t < ende_raetsel + self.t_zeit_um:
            self._szene_zeit_um(bild, t - ende_raetsel)
        else:
            self._szene_ende(bild, t - ende_raetsel - self.t_zeit_um)
        if self.wasserzeichen:
            ebene, pos = self.wasserzeichen
            bild.alpha_composite(ebene, dest=pos)
        return bild.convert("RGB")

    def _ausblenden(self, t, dauer):
        """Faktor für das Ausblenden am Ende einer Szene."""
        if self.t_uebergang <= 0:
            return 1.0
        return clamp((dauer - t) / self.t_uebergang)

    def _woerter_zeigen(self, ebene, boxen, t, intervall, dauer, hub):
        """Baut die Text-Ebene Wort für Wort auf: jedes Wort gleitet von unten herein."""
        if t >= (len(boxen) - 1) * intervall + dauer:
            return ebene
        aufbau = Image.new("RGBA", ebene.size, (0, 0, 0, 0))
        for i, (x0, y0, x1, y1) in enumerate(boxen):
            p = ease_out((t - i * intervall) / dauer)
            if p <= 0:
                break
            stueck = ebene.crop((x0, y0, x1, y1))
            dy = round(hub * (1 - p))
            platz = aufbau.height - (y0 + dy)
            if platz <= 0:
                continue
            if stueck.height > platz:
                stueck = stueck.crop((0, 0, stueck.width, platz))
            aufbau.alpha_composite(mit_deckkraft(stueck, p), dest=(x0, y0 + dy))
        return aufbau

    def _glow(self, bild, t, mitte_y, deckkraft):
        if self.glow_ebene is None:
            return
        atmen = 0.75 + 0.25 * math.sin(2 * math.pi * t / 2.5)
        einfuegen(bild, self.glow_ebene, (self.mitte_x, mitte_y), deckkraft * atmen)

    def _szene_hook(self, bild, t):
        raus = self._ausblenden(t, self.t_hook)
        hoehe_unter = self.hook_unter_ebene.height + 50 if self.hook_unter_ebene else 0
        mitte_y = self.mitte_y - hoehe_unter / 2
        self._glow(bild, t, mitte_y, ease_out(t / 0.6) * raus)

        ebene = self._woerter_zeigen(self.hook_ebene, self.hook_boxen, t, 0.12, 0.3, 30)
        skalierung = 0.8 + 0.2 * ease_out_back(t / 0.55)
        einfuegen(bild, ebene, (self.mitte_x, mitte_y), raus, skalierung)

        if self.hook_unter_ebene:
            start = min(0.55, self.t_hook * 0.4)
            p = ease_out((t - start) / 0.35)
            y = mitte_y + self.hook_ebene.height / 2 + 50 + self.hook_unter_ebene.height / 2 + 20 * (1 - p)
            einfuegen(bild, self.hook_unter_ebene, (self.mitte_x, y), p * raus)

    def _szene_raetsel(self, bild, t):
        a = self.cfg["animation"]
        dauer_ein = max(0.01, a["einblenden_dauer"])
        raus = self._ausblenden(t, self.t_raetsel)
        c = t - self.t_lesen                       # Sekunden seit Countdown-Start
        rest_sek = self.t_countdown - max(c, 0)
        kritisch = c >= 0 and rest_sek <= self.kritisch_ab
        in_sekunde = max(c, 0) - math.floor(max(c, 0))
        warn_anteil = clamp((self.kritisch_ab - rest_sek + 0.3) / 0.3) if c >= 0 else 0.0

        # Roter Rand pulsiert in den letzten Sekunden mit jedem Tick
        if self.vignette is not None and kritisch:
            einfuegen(bild, self.vignette, (self.breite / 2, self.hoehe / 2),
                      (0.35 + 0.65 * (1 - ease_out(in_sekunde / 0.6))) * raus)

        text_mitte_y = (self.text_oben + self.text_unten) / 2
        self._glow(bild, t, text_mitte_y, ease_out(t / dauer_ein) * raus)

        # Label
        p_label = ease_out(t / dauer_ein)
        einfuegen(bild, self.label_ebene, (self.mitte_x, self.label_y + 20 * (1 - p_label)), p_label * raus)

        # Rätseltext Wort für Wort, dann langsames Heranzoomen und ein „Herzschlag“ in der Schlussphase
        ebene = self._woerter_zeigen(self.text_ebene, self.text_boxen, t - 0.15, self.text_intervall,
                                     self.wort_dauer, 24)
        if self.bild_ebene is not None:
            kombi = Image.new("RGBA", (max(self.bild_ebene.width, ebene.width), self.bild_versatz + ebene.height),
                              (0, 0, 0, 0))
            p_bild = ease_out(t / dauer_ein)
            kombi.alpha_composite(mit_deckkraft(self.bild_ebene, p_bild),
                                  ((kombi.width - self.bild_ebene.width) // 2, 0))
            kombi.alpha_composite(ebene, ((kombi.width - ebene.width) // 2, self.bild_versatz))
            ebene = kombi
        zoom = 1 + a["zoom_drift"] * (t / self.t_raetsel)
        if kritisch:
            zoom *= 1 + 0.02 * (1 - ease_out(in_sekunde / 0.4))
        einfuegen(bild, ebene, (self.mitte_x, text_mitte_y), raus, zoom)

        # Countdown
        if c < -0.3:
            return
        stil = self.cfg["countdown"].get("stil", "ring")
        p_cd = ease_out((c + 0.3) / 0.4) * raus
        rest = clamp(1 - c / self.t_countdown)
        farbe = farbmix(self.akzent, self.warnung, warn_anteil)

        wackeln = 0.0
        if kritisch:
            wackeln = 9 * math.sin(2 * math.pi * 16 * in_sekunde) * (1 - ease_out(in_sekunde / 0.35))

        if stil == "ring":
            einfuegen(bild, self._ring(rest, farbe), (self.mitte_x + wackeln, self.countdown_y), p_cd)

        if stil in ("ring", "zahlen", "beides"):
            n = int(clamp(math.ceil(self.t_countdown - math.floor(max(c, 0))), 1, math.ceil(self.t_countdown)))
            staerke = a["countdown_puls"] * (1.8 if kritisch else 1.0)
            puls = 1 + staerke * (1 - ease_out(in_sekunde / 0.3))
            ebene = self.zahl_ebenen.get((n, self.warnung if warn_anteil > 0.5 else self.akzent))
            if ebene is not None:
                einfuegen(bild, ebene, (self.mitte_x + wackeln, self.countdown_y), p_cd, puls)

        if stil in ("balken", "beides"):
            g = self.cfg["groessen"]
            bb, bh = g["countdown_balken_breite"], g["countdown_balken_hoehe"]
            balken = Image.new("RGBA", (bb, bh), (0, 0, 0, 0))
            d = ImageDraw.Draw(balken)
            d.rounded_rectangle((0, 0, bb - 1, bh - 1), radius=bh // 2, fill=self.balken_hg)
            fuell = round(bb * rest)
            if fuell >= bh:
                d.rounded_rectangle((0, 0, fuell - 1, bh - 1), radius=bh // 2, fill=farbe)
            einfuegen(bild, balken, (self.mitte_x, self.balken_y), p_cd)

    def _ring(self, rest, farbe):
        """Kreisförmiger Timer; doppelt so groß gezeichnet und verkleinert für glatte Kanten."""
        faktor = 2
        d = self.ring_d * faktor
        staerke = self.cfg["groessen"].get("countdown_ring_staerke", 18) * faktor
        ring = Image.new("RGBA", (d, d), (0, 0, 0, 0))
        zeichnen = ImageDraw.Draw(ring)
        zeichnen.ellipse((0, 0, d - 1, d - 1), outline=self.balken_hg, width=staerke)
        if rest > 0.002:
            ende = -90 + 360 * rest
            zeichnen.arc((0, 0, d - 1, d - 1), start=-90, end=ende, fill=farbe, width=staerke)
            # abgerundete Enden
            r_mitte = (d - staerke) / 2
            for winkel in (-90, ende):
                bogen = math.radians(winkel)
                cx = d / 2 + r_mitte * math.cos(bogen)
                cy = d / 2 + r_mitte * math.sin(bogen)
                zeichnen.ellipse((cx - staerke / 2, cy - staerke / 2, cx + staerke / 2, cy + staerke / 2), fill=farbe)
        return ring.resize((self.ring_d, self.ring_d), Image.LANCZOS)

    def _szene_zeit_um(self, bild, t):
        if self.vignette is not None:
            einfuegen(bild, self.vignette, (self.breite / 2, self.hoehe / 2), 1 - ease_out(t / 0.7))
        if self.zeit_um_ebene is None:
            return
        raus = self._ausblenden(t, self.t_zeit_um)
        skalierung = 1.5 - 0.5 * ease_out_back(t / 0.3)
        wackeln = 14 * math.sin(2 * math.pi * 14 * t) * (1 - ease_out(t / 0.4))
        einfuegen(bild, self.zeit_um_ebene, (self.mitte_x + wackeln, self.mitte_y), ease_out(t / 0.12) * raus,
                  skalierung)

    def _szene_ende(self, bild, t):
        self._glow(bild, t, self.mitte_y, ease_out(t / 0.5))
        abstand = 70
        h1, h2 = self.end1_ebene.height, self.end2_ebene.height
        h3 = self.handle_ebene.height if self.handle_ebene else 0
        gesamt = h1 + abstand + h2 + (abstand * 0.6 + h3 if h3 else 0)
        y = self.mitte_y - gesamt / 2

        def pop(ebene, y_mitte, start):
            p = (t - start) / 0.4
            if p > 0:
                einfuegen(bild, ebene, (self.mitte_x, y_mitte), ease_out(p * 2), 0.7 + 0.3 * ease_out_back(p))

        pop(self.end1_ebene, y + h1 / 2, 0.0)
        y += h1 + abstand
        # „Folge für die Auflösung“ pulsiert danach sanft weiter
        pop_zeit = max(0.0, t - 0.65)
        puls = 1 + 0.035 * math.sin(2 * math.pi * pop_zeit / 0.9) if pop_zeit > 0 else 1.0
        if t > 0.25:
            p = (t - 0.25) / 0.4
            einfuegen(bild, self.end2_ebene, (self.mitte_x, y + h2 / 2), ease_out(p * 2),
                      (0.7 + 0.3 * ease_out_back(p)) * puls)
        if self.handle_ebene:
            y += h2 + abstand * 0.6
            einfuegen(bild, self.handle_ebene, (self.mitte_x, y + h3 / 2), ease_out((t - 0.5) / 0.4))

    def vorschau_zeitpunkt(self):
        """Zeitpunkt für das Vorschaubild: Rätsel vollständig sichtbar, Countdown läuft gerade an."""
        return self.t_hook + self.t_lesen + 0.4
