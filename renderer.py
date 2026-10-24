"""Erzeugt die einzelnen Video-Frames für ein Rätsel mit Pillow."""

import math
import os
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

EMOJI_RENDER_GROESSE = 109  # Noto Color Emoji ist eine Bitmap-Schrift und gibt es nur in dieser Größe
UNSICHTBAR = {"️", "‍"} | {chr(c) for c in range(0x1F3FB, 0x1F400)}  # inkl. Hautfarben
FEHLENDE_EMOJI = set()


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


@lru_cache(maxsize=4)
def emoji_schrift(pfad):
    try:
        return ImageFont.truetype(pfad, EMOJI_RENDER_GROESSE)
    except OSError:
        return None


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
        self.emoji_schrift = emoji_schrift(emoji_pfad) if emoji_pfad and os.path.exists(emoji_pfad) else None
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
            if bild is None and zeichen not in FEHLENDE_EMOJI:
                FEHLENDE_EMOJI.add(zeichen)
                print(f"  ⚠ Emoji „{zeichen}“ (U+{ord(zeichen):04X}) kann nicht dargestellt werden und fehlt im Video.")
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

def buchstaben_text(anzahl):
    """2 → „A oder B“, 3 → „A, B oder C“ – für Aufrufe wie „A, B oder C? Ab in die Kommentare“."""
    buchstaben = list("ABCD"[:anzahl])
    if len(buchstaben) < 2:
        return "".join(buchstaben)
    return ", ".join(buchstaben[:-1]) + " oder " + buchstaben[-1]


def countdown_fuer(cfg, raetsel):
    """Countdown-Länge: eigener Wert im Rätsel (`countdown`), sonst je Schwierigkeit aus der Config."""
    if raetsel.get("countdown"):
        return float(raetsel["countdown"])
    wert = cfg["zeiten"]["countdown"]
    if isinstance(wert, dict):
        stufe = str(raetsel.get("schwierigkeit", "")).lower()
        wert = wert.get(stufe, wert.get("standard", 10))
    return float(wert)


def lesezeit_fuer(cfg, raetsel):
    """Zeit zum Lesen, bevor der Countdown startet – je länger der Rätseltext, desto mehr Zeit."""
    if raetsel.get("lesezeit"):
        return float(raetsel["lesezeit"])
    wert = cfg["zeiten"]["lesezeit"]
    if not isinstance(wert, dict):
        return float(wert)
    zeichen = len(str(raetsel["frage"]).replace("*", ""))
    return clamp(zeichen / wert.get("zeichen_pro_sekunde", 14), wert.get("min", 1.5), wert.get("max", 10))


def waehle(wert, zufall, schwierigkeit=None):
    """Texte dürfen ein String, eine Liste (zufällige Auswahl) oder ein Dict je Schwierigkeit sein."""
    if isinstance(wert, dict):
        wert = wert.get(schwierigkeit) or wert.get("standard") or next(iter(wert.values()), None)
    if isinstance(wert, list):
        return zufall.choice(wert) if wert else None
    return wert


class RaetselRenderer:
    """Ablauf: Rätsel ab dem ersten Frame (mit wechselnden Sprüchen) → Lesezeit → Countdown (Denkzeit) →
    „Zeit um!“ → Kommentar-Pause „Auflösung in 3·2·1“ → Auflösung mit Erklärung → Abschluss
    („Hattest du's?“) → Überblendung zurück zum ersten Frame, damit das Video nahtlos loopt.
    Ohne Auflösung (`aufloesung.zeigen = false`) folgt auf „Zeit um!“ die Endkarte."""

    def __init__(self, config, raetsel, basis_pfad):
        self.cfg = config
        self.raetsel = raetsel
        self.basis = basis_pfad
        v = config["video"]
        self.breite, self.hoehe, self.fps = v["breite"], v["hoehe"], v["fps"]

        self.kat = config["kategorien"].get(raetsel["kategorie"], {})
        self.texte = {**config["texte"], **self.kat.get("texte", {})}
        self.zufall = random.Random(f"{raetsel['id']}-{raetsel['kategorie']}")  # gleiche ID → gleiche Sprüche
        self.schwierigkeit = str(raetsel.get("schwierigkeit", "")).lower()
        self.typ = raetsel.get("typ", "text")
        self.optionen = [str(o) for o in raetsel.get("optionen") or []]

        farben = config["farben"]
        self.hintergrund = hex_zu_rgb(farben["hintergrund"]) + (255,)
        self.textfarbe = hex_zu_rgb(farben["text"]) + (255,)
        self.akzent = hex_zu_rgb(self.kat.get("akzent") or farben["akzent"]) + (255,)
        self.warnung = hex_zu_rgb(farben.get("warnung", "#FF4D4D")) + (255,)
        self.dezent = hex_zu_rgb(farben["dezent"]) + (255,)
        self.label_textfarbe = hex_zu_rgb(farben["label_text"]) + (255,)
        self.balken_hg = hex_zu_rgb(farben["balken_hintergrund"]) + (255,)
        self.option_fuellung = hex_zu_rgb(farben.get("option_hintergrund", "#141414")) + (255,)
        self.option_rand = hex_zu_rgb(farben.get("option_rand", "#464646")) + (255,)

        s = config["schriften"]
        self.fett_pfad = self._pfad(s["fett"])
        self.normal_pfad = self._pfad(s.get("normal") or s["fett"])
        emoji_pfad = self._pfad(s["emoji"]) if s.get("emoji") else None
        self.setzer_fett = TextSetzer(self.fett_pfad, emoji_pfad)
        self.setzer_normal = TextSetzer(self.normal_pfad, emoji_pfad)

        z = config["zeiten"]
        self.t_lesen = lesezeit_fuer(config, raetsel)          # ohne Zeitdruck: noch kein Countdown
        self.t_countdown = countdown_fuer(config, raetsel)     # reine Denkzeit
        self.t_raetsel = self.t_lesen + self.t_countdown
        self.t_zeit_um = z.get("zeit_um", 0)
        self.t_uebergang = z["uebergang"]
        self.aufl = config.get("aufloesung", {})
        self.mit_aufloesung = bool(self.aufl.get("zeigen"))
        if self.mit_aufloesung:
            self.t_pause = self.aufl.get("pause", 2.1)
            if self.typ == "finde":
                self.t_aufloesung = self.aufl.get("min_dauer", 3.5)
            else:  # so lange, dass man die Erklärung in Ruhe lesen kann
                lesen = len(str(raetsel.get("erklaerung", ""))) / self.aufl.get("zeichen_pro_sekunde", 14)
                self.t_aufloesung = clamp(self.aufl.get("grunddauer", 1.8) + lesen,
                                          self.aufl.get("min_dauer", 3.5), self.aufl.get("max_dauer", 8))
            self.t_abschluss = z.get("abschluss", 2.4)
            self.t_end = self.t_pause + self.t_aufloesung + self.t_abschluss
            letzte_szene = self.t_abschluss
        else:
            self.t_end = z["endkarte"]
            letzte_szene = self.t_end
        self.t_loop = min(z.get("loop", 0), letzte_szene)
        self.dauer = self.t_raetsel + self.t_zeit_um + self.t_end

        self.anim = config["animation"]
        # Schlussphase: höchstens `kritisch_ab` Sekunden, bei kurzen Countdowns entsprechend kürzer
        self.kritisch_ab = min(self.anim.get("kritisch_ab", 3), max(2, round(self.t_countdown * 0.4)))

        self._layout()
        self._ebenen_vorbereiten()
        self._partikel_vorbereiten()
        self._frame0 = None

    def _pfad(self, p):
        return p if os.path.isabs(p) else os.path.join(self.basis, p)

    def _text(self, schluessel):
        text = waehle(self.texte.get(schluessel), self.zufall, self.schwierigkeit)
        if not text:
            return text
        return text.replace("{countdown}", str(round(self.t_countdown))).replace(
            "{buchstaben}", buchstaben_text(len(self.optionen)))

    @property
    def frame_anzahl(self):
        return round(self.dauer * self.fps)

    # ---- Zeitpunkte für Ton und Musik (Sekunden ab Videostart)
    def countdown_start(self):
        return self.t_lesen

    def zeit_um_zeitpunkt(self):
        return self.t_raetsel

    def pause_start(self):
        return self.t_raetsel + self.t_zeit_um

    def pause_ticks(self):
        """Zeitpunkte der Zahlen 3 · 2 · 1 vor der Auflösung."""
        if not self.mit_aufloesung:
            return []
        return [self.pause_start() + i * self.t_pause / 3 for i in range(3)]

    def aufloesung_zeitpunkt(self):
        return self.pause_start() + self.t_pause if self.mit_aufloesung else None

    def tipp_zeitpunkt(self):
        return self._tipp_start

    def ticks(self):
        """Liste (zeit, kritisch) – ein Tick pro Countdown-Sekunde."""
        n = math.ceil(self.t_countdown)
        return [(self.t_lesen + i, n - i <= self.kritisch_ab) for i in range(n)]

    def vorschau_zeitpunkt(self):
        """Zeitpunkt für das Vorschaubild: alles eingeblendet, Countdown läuft gerade an."""
        return self.t_lesen + 0.5

    def aufloesung_vorschau_zeitpunkt(self):
        """Zeitpunkt für das zweite Vorschaubild: Lösung und Erklärung vollständig sichtbar."""
        return self.aufloesung_zeitpunkt() + min(2.2, self.t_aufloesung - 0.3) if self.mit_aufloesung else None

    # ---- Layout innerhalb der TikTok-Safe-Zones
    def _layout(self):
        sz = self.cfg["safe_zone"]
        g = self.cfg["groessen"]
        self.inhalt_links = sz["links"]
        self.inhalt_rechts = self.breite - sz["rechts"]
        self.inhalt_oben = sz["oben"]
        self.inhalt_unten = self.hoehe - sz["unten"]
        self.inhalt_breite = self.inhalt_rechts - self.inhalt_links
        self.mitte_x = (self.inhalt_links + self.inhalt_rechts) / 2
        self.mitte_y = (self.inhalt_oben + self.inhalt_unten) / 2
        hoehe = self.inhalt_unten - self.inhalt_oben

        # Mit Antworten oder Such-Gitter wird der Countdown-Ring kleiner, damit mehr Platz bleibt
        kompakt = bool(self.optionen) or self.typ == "finde"
        self.ring_d = g["countdown_ring_klein"] if kompakt else g["countdown_ring_durchmesser"]
        self.countdown_y = self.inhalt_unten - self.ring_d / 2 - 30
        self.balken_y = self.countdown_y + self.ring_d / 2 - 10
        self.label_y = self.inhalt_oben + 0.08 * hoehe
        self.banner_y = self.label_y + g.get("banner_abstand", 95)
        self.bereich_oben = self.banner_y + 60
        self.bereich_unten = self.countdown_y - self.ring_d / 2 - 40

    # ---- Ebenen, die sich nicht pro Frame ändern
    def _ebenen_vorbereiten(self):
        g = self.cfg["groessen"]
        textbreite = self.inhalt_breite - 20

        self._label_vorbereiten()
        self._optionen_vorbereiten(textbreite)
        self.inhalt_ebene = self._inhalt(textbreite, self.text_unten - self.bereich_oben)
        self.inhalt_y = (self.bereich_oben + self.text_unten) / 2
        self._banner_vorbereiten(textbreite)

        # Countdown-Zahlen in Normal- und Warnfarbe
        zahl_groesse = round(g["countdown_zahl"] * self.ring_d / 280)
        self.zahl_ebenen = {}
        for n in range(1, math.ceil(self.t_countdown) + 1):
            for farbe in (self.akzent, self.warnung):
                self.zahl_ebenen[(n, farbe)] = self.setzer_fett.block(str(n), zahl_groesse, 400, farbe, farbe, 1.0)

        # „Zeit um!“ und Endkarte
        self.zeit_um_ebene = None
        zeit_um = self._text("zeit_um")
        if self.t_zeit_um > 0 and zeit_um:
            self.zeit_um_ebene = self._einzeilig(self.setzer_fett, zeit_um, g.get("zeit_um", 130), textbreite,
                                                 self.warnung, self.textfarbe, 70)
        handle = self.texte.get("handle")
        self.handle_ebene = self.setzer_normal.block(handle, g["handle"], textbreite, self.dezent,
                                                     self.akzent, 1.2) if handle else None
        if self.mit_aufloesung:
            self._aufloesung_vorbereiten(textbreite)
        else:
            end1 = (self._text("endkarte_1_optionen") if self.optionen else None) or self._text("endkarte_1")
            self.end1_ebene = self.setzer_fett.block(end1, g["endkarte_1"], textbreite, self.textfarbe,
                                                     self.akzent, 1.2)
            self.end2_ebene = self.setzer_fett.block(self._text("endkarte_2"), g["endkarte_2"], textbreite,
                                                     self.akzent, self.textfarbe, 1.2)

        # Hintergrund: weiches Leuchten hinter dem Inhalt, roter Rand für die Schlussphase
        a = self.anim
        self.glow_ebene = None
        if a.get("glow_deckkraft", 0) > 0:
            d = round(self.inhalt_breite * 1.25)
            self.glow_ebene = radialer_verlauf(d, d, self.akzent, a["glow_deckkraft"], 0.0, 1.4)
        self.vignette = None
        if a.get("vignette_deckkraft", 0) > 0:
            self.vignette = radialer_verlauf(self.breite, self.hoehe, self.warnung, 0.0, a["vignette_deckkraft"], 2.2)

        self._wasserzeichen_vorbereiten()

    def _label_vorbereiten(self):
        self.label_ebene = self._pille(self.kat.get("label") or self.raetsel["kategorie"].upper(), self.akzent)

    def _pille(self, text, farbe):
        """Gefüllte Plakette mit Text, z. B. „IQ-TEST“ oder „AUFLÖSUNG“."""
        g = self.cfg["groessen"]
        f = schrift(self.fett_pfad, g["label"])
        box = f.getbbox(text, anchor="ls")
        pad_x, pad_y = round(g["label"] * 0.7), round(g["label"] * 0.45)
        w = (box[2] - box[0]) + 2 * pad_x
        h = (box[3] - box[1]) + 2 * pad_y
        ebene = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(ebene)
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=farbe)
        d.text((pad_x - box[0], pad_y - box[1]), text, font=f, fill=self.label_textfarbe, anchor="ls")
        return ebene

    def _stapel(self, zeilen):
        """Ebenen (mit Abstand danach) untereinander, als Gruppe senkrecht mittig: Liste der Mittelpunkte (y)."""
        hoehe = sum(e.height + abstand for e, abstand in zeilen) - (zeilen[-1][1] if zeilen else 0)
        y, mitten = self.mitte_y - hoehe / 2, []
        for ebene, abstand in zeilen:
            mitten.append(y + ebene.height / 2)
            y += ebene.height + abstand
        return mitten

    def _aufloesung_vorbereiten(self, textbreite):
        """Ebenen für Kommentar-Pause, Auflösung und Abschluss."""
        g = self.cfg["groessen"]
        r = self.raetsel
        self.loesungsfarbe = hex_zu_rgb(self.cfg["farben"].get("loesung", "#6FCF97")) + (255,)

        self.pause_zeilen = [
            (self.setzer_fett.block(self._text("pause_1"), g.get("pause_1", 84), textbreite,
                                    self.textfarbe, self.akzent, 1.15), 30),
            (self.setzer_fett.block(self._text("pause_2"), g.get("pause_2", 52), textbreite,
                                    self.textfarbe, self.akzent, 1.25), 110),
            (self.setzer_fett.block(self._text("pause_3"), g.get("pause_3", 52), textbreite,
                                    self.dezent, self.akzent, 1.2), 10),
        ]
        self.pause_zahlen = {n: self.setzer_fett.block(str(n), g.get("pause_zahl", 200), 400, self.akzent,
                                                       self.akzent, 1.0) for n in (1, 2, 3)}
        self.pause_mitten = self._stapel(self.pause_zeilen + [(self.pause_zahlen[3], 0)])

        self.loesung_label = self._pille(self._text("aufloesung_label") or "AUFLÖSUNG", self.loesungsfarbe)
        loesung = str(r["loesung"])
        if self.typ == "finde":
            self.loesung_ebene = self._einzeilig(self.setzer_fett, loesung, g.get("loesung_finde", 72), textbreite,
                                                 self.akzent, self.akzent, 40)
        else:
            self.kontext_ebene = mit_deckkraft(self.setzer_normal.block(
                r["frage"], g.get("kontext", 38), textbreite, self.dezent, self.dezent, 1.25), 0.85)
            groesse = self.setzer_fett.passende_groesse(loesung, textbreite, g.get("loesung", 150) * 2.3,
                                                        g.get("loesung", 150), 60, 1.05)
            self.loesung_ebene = self.setzer_fett.block(loesung, groesse, textbreite, self.akzent, self.akzent, 1.05)
            platz = (self.inhalt_unten - 40) - self.bereich_oben - self.kontext_ebene.height \
                - self.loesung_ebene.height - 50 - 40
            groesse = self.setzer_fett.passende_groesse(r["erklaerung"], textbreite, platz,
                                                        g.get("erklaerung", 56), 32, 1.3)
            self.erklaerung_ebene = self.setzer_fett.block(r["erklaerung"], groesse, textbreite, self.textfarbe,
                                                          self.akzent, 1.3)
            hoehe = self.kontext_ebene.height + 50 + self.loesung_ebene.height + 40 + self.erklaerung_ebene.height
            y = (self.bereich_oben + self.inhalt_unten - 40) / 2 - hoehe / 2
            self.kontext_y = y + self.kontext_ebene.height / 2
            y += self.kontext_ebene.height + 50
            self.loesung_y = y + self.loesung_ebene.height / 2
            y += self.loesung_ebene.height + 40
            self.erklaerung_y = y + self.erklaerung_ebene.height / 2

        self.abschluss_zeilen = [
            (self.setzer_fett.block(self._text("abschluss_1"), g.get("abschluss_1", 110), textbreite,
                                    self.textfarbe, self.akzent, 1.1), 50),
            (self.setzer_fett.block(self._text("abschluss_2"), g.get("abschluss_2", 70), textbreite,
                                    self.textfarbe, self.akzent, 1.25), 40),
            (self.setzer_fett.block(self._text("abschluss_3"), g.get("abschluss_3", 52), textbreite,
                                    self.akzent, self.textfarbe, 1.2), 50),
        ]
        if self.handle_ebene:
            self.abschluss_zeilen.append((self.handle_ebene, 0))
        self.abschluss_mitten = self._stapel(self.abschluss_zeilen)

    def _einzeilig(self, setzer, text, groesse, breite, farbe, akzent, min_groesse=28):
        """Text so klein wie nötig setzen, damit er in eine Zeile passt."""
        while groesse > min_groesse and len(setzer.umbrechen(text, groesse, breite)[0]) > 1:
            groesse -= 2
        return setzer.block(text, groesse, breite, farbe, akzent, 1.15)

    def _banner_vorbereiten(self, textbreite):
        """Spruch-Zeile über dem Rätsel: Hook → (Tipp oder Spruch zur Mitte) → Spruch für die Schlussphase."""
        g = self.cfg["groessen"]
        a = self.anim
        groesse = g.get("banner", 50)
        self.banner = []
        hook = self.raetsel.get("hook") or self._text("hook")
        if hook:
            self.banner.append((0.0, self._einzeilig(self.setzer_fett, hook, groesse, textbreite,
                                                     self.akzent, self.textfarbe)))
        self._tipp_start = None
        frueheste = self.t_lesen + 1.5  # der Hook soll mindestens so lange stehen bleiben
        if self.raetsel.get("tipp"):
            self._tipp_start = max(frueheste, self.t_raetsel - min(a.get("tipp_ab", 5), self.t_countdown / 2))
            tipp = (self.texte.get("tipp_prefix") or "") + self.raetsel["tipp"]
            self.banner.append((self._tipp_start, self._einzeilig(self.setzer_fett, tipp, groesse, textbreite,
                                                                  self.textfarbe, self.akzent)))
        else:
            mitte = self._text("spruch_mitte")
            mitte_start = max(frueheste, self.t_raetsel - a.get("spruch_mitte_ab", 6))
            if mitte and mitte_start < self.t_raetsel - self.kritisch_ab - 1.0:  # bei kurzen Countdowns weglassen
                self.banner.append((mitte_start, self._einzeilig(self.setzer_fett, mitte, groesse, textbreite,
                                                                 self.textfarbe, self.akzent)))
            schluss = self._text("spruch_kritisch")
            if schluss:
                self.banner.append((self.t_raetsel - self.kritisch_ab,
                                    self._einzeilig(self.setzer_fett, schluss, groesse, textbreite,
                                                    self.warnung, self.textfarbe)))
        self.banner.sort(key=lambda eintrag: eintrag[0])

    def _optionen_vorbereiten(self, textbreite):
        """Antwort-Kästen A/B/C; kurze Antworten nebeneinander, lange untereinander."""
        g = self.cfg["groessen"]
        self.optionen_ebenen = []
        self.text_unten = self.bereich_unten
        if not self.optionen:
            return
        n = len(self.optionen)
        hoehe, abstand = g.get("option_hoehe", 112), g.get("option_abstand", 20)
        nebeneinander = n <= 4 and all(len(o) <= 6 for o in self.optionen)
        if nebeneinander:
            breite = int((textbreite - (n - 1) * abstand) / n)
            gesamt = hoehe
        else:
            breite = min(800, textbreite)
            gesamt = n * hoehe + (n - 1) * abstand
        oben = self.bereich_unten - gesamt
        for i, text in enumerate(self.optionen):
            ebene, warn = self._option_ebenen("ABCD"[i], text, breite, hoehe)
            if nebeneinander:
                links = self.mitte_x - textbreite / 2
                mitte = (links + i * (breite + abstand) + breite / 2, oben + hoehe / 2)
            else:
                mitte = (self.mitte_x, oben + i * (hoehe + abstand) + hoehe / 2)
            self.optionen_ebenen.append((ebene, warn, mitte))
        self.text_unten = oben - 40

    def _option_ebenen(self, buchstabe, text, breite, hoehe):
        """Antwort-Kasten mit Buchstaben-Plakette – dazu eine Ebene nur mit rotem Rand fürs Pulsieren."""
        g = self.cfg["groessen"]
        radius = min(30, hoehe // 2)
        ebene = Image.new("RGBA", (breite, hoehe), (0, 0, 0, 0))
        d = ImageDraw.Draw(ebene)
        d.rounded_rectangle((0, 0, breite - 1, hoehe - 1), radius=radius, fill=self.option_fuellung,
                            outline=self.option_rand, width=3)
        k = hoehe - 30
        d.ellipse((15, 15, 15 + k, 15 + k), fill=self.akzent)
        d.text((15 + k / 2, 15 + k / 2 + 2), buchstabe, font=schrift(self.fett_pfad, round(k * 0.58)),
               fill=self.label_textfarbe, anchor="mm")
        links = 15 + k + 26
        text_ebene = self._einzeilig(self.setzer_fett, text, g.get("option_text", 54), breite - links - 18,
                                     self.textfarbe, self.akzent, 24)
        ebene.alpha_composite(text_ebene, (links, max(0, round((hoehe - text_ebene.height) / 2) + 2)))
        warn = Image.new("RGBA", (breite, hoehe), (0, 0, 0, 0))
        ImageDraw.Draw(warn).rounded_rectangle((0, 0, breite - 1, hoehe - 1), radius=radius,
                                               outline=self.warnung, width=5)
        return ebene, warn

    def _inhalt(self, max_b, max_h):
        """Die eigentliche Rätsel-Ebene: Text (optional mit Bild darüber) oder Such-Gitter."""
        if self.typ == "finde":
            return self._finde_ebene(max_b, max_h)
        g = self.cfg["groessen"]
        frage = self.raetsel["frage"]
        zeilenabstand = self.kat.get("zeilenabstand", g["zeilenabstand"])
        max_groesse = self.kat.get("raetsel_max", g["raetsel_max"])
        bild_ebene = None
        if self.raetsel.get("bild"):
            pfad = self._pfad(self.raetsel["bild"])
            if not os.path.exists(pfad):
                raise FileNotFoundError(f"Bild für Rätsel {self.raetsel['id']} nicht gefunden: {pfad}")
            bild = Image.open(pfad).convert("RGBA")
            faktor = min(max_b / bild.width, max_h * 0.55 / bild.height)
            bild_ebene = bild.resize((round(bild.width * faktor), round(bild.height * faktor)), Image.LANCZOS)
            max_h -= bild_ebene.height + 40
        groesse = self.setzer_fett.passende_groesse(frage, max_b, max_h, max_groesse, g["raetsel_min"],
                                                    zeilenabstand)
        self.raetsel_schriftgroesse = groesse
        text = self.setzer_fett.block(frage, groesse, max_b, self.textfarbe, self.akzent, zeilenabstand)
        if bild_ebene is None:
            return text
        kombi = Image.new("RGBA", (max(bild_ebene.width, text.width), bild_ebene.height + 40 + text.height),
                          (0, 0, 0, 0))
        kombi.alpha_composite(bild_ebene, ((kombi.width - bild_ebene.width) // 2, 0))
        kombi.alpha_composite(text, ((kombi.width - text.width) // 2, bild_ebene.height + 40))
        return kombi

    def _finde_ebene(self, max_b, max_h):
        """Gitter aus gleichen Zeichen mit genau einem abweichenden – inklusive Reihen-/Spaltennummern."""
        r = self.raetsel
        g = self.cfg["groessen"]
        frage = self._einzeilig(self.setzer_fett, r["frage"], g.get("finde_frage", 64), max_b,
                                self.textfarbe, self.akzent)
        spalten, zeilen = int(r["spalten"]), int(r["zeilen"])
        ziel_reihe, ziel_spalte = (int(x) for x in r["position"])
        rand, abstand = 46, 26
        zelle = int(min((max_b - 2 * rand) / spalten, (max_h - frage.height - abstand - rand) / zeilen))
        groesse = max(18, round(zelle * 0.74))
        self.raetsel_schriftgroesse = groesse

        def glyphe(zeichen, farbe):
            ebene = self.setzer_fett.block(str(zeichen), groesse, zelle * 4, farbe, farbe, 1.0)
            box = ebene.getbbox()
            return ebene.crop(box) if box else ebene

        def gitter_bauen(aufloesung):
            """aufloesung=True: alle anderen Zeichen blass, das gesuchte farbig und eingekreist."""
            normal = glyphe(r["zeichen"], self.textfarbe)
            ziel = glyphe(r["ziel"], self.akzent if aufloesung else self.textfarbe)
            if aufloesung:
                normal = mit_deckkraft(normal, 0.25)
            breite = 2 * rand + spalten * zelle  # rechts gleich viel Rand wie links → Gitter wirkt mittig
            gitter = Image.new("RGBA", (breite, rand + zeilen * zelle), (0, 0, 0, 0))
            d = ImageDraw.Draw(gitter)
            nummer = schrift(self.normal_pfad, max(16, min(30, round(zelle * 0.34))))
            for s in range(spalten):
                farbe = self.akzent if aufloesung and s + 1 == ziel_spalte else self.dezent
                d.text((rand + s * zelle + zelle / 2, rand / 2), str(s + 1), font=nummer, fill=farbe, anchor="mm")
            for z in range(zeilen):
                farbe = self.akzent if aufloesung and z + 1 == ziel_reihe else self.dezent
                d.text((rand / 2, rand + z * zelle + zelle / 2), str(z + 1), font=nummer, fill=farbe, anchor="mm")
                for s in range(spalten):
                    bild = ziel if (z + 1, s + 1) == (ziel_reihe, ziel_spalte) else normal
                    gitter.alpha_composite(bild, (round(rand + s * zelle + (zelle - bild.width) / 2),
                                                  round(rand + z * zelle + (zelle - bild.height) / 2)))
            if aufloesung:
                cx, cy = rand + (ziel_spalte - 0.5) * zelle, rand + (ziel_reihe - 0.5) * zelle
                radius = zelle * 0.48
                d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=self.akzent,
                          width=max(4, round(zelle * 0.07)))
            gesamt = Image.new("RGBA", (max(frage.width, gitter.width), frage.height + abstand + gitter.height),
                               (0, 0, 0, 0))
            gesamt.alpha_composite(frage, ((gesamt.width - frage.width) // 2, 0))
            gesamt.alpha_composite(gitter, ((gesamt.width - gitter.width) // 2, frage.height + abstand))
            return gesamt

        self.finde_aufloesung_ebene = gitter_bauen(True)
        return gitter_bauen(False)

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

    def _partikel_vorbereiten(self):
        """Langsam aufsteigende Lichtpunkte im Hintergrund – geben dem schwarzen Bild Tiefe."""
        zufall = random.Random(f"partikel-{self.raetsel['id']}")
        self.partikel = [(zufall.uniform(0, self.breite), zufall.uniform(0, self.hoehe), zufall.uniform(15, 45),
                          zufall.uniform(1.5, 4.0), zufall.uniform(0.12, 0.4), zufall.uniform(0, 2 * math.pi))
                         for _ in range(int(self.anim.get("partikel", 0)))]

    # ---- Frame-Erzeugung
    def frame(self, t):
        bild = Image.new("RGBA", (self.breite, self.hoehe), self.hintergrund)
        self._partikel(bild, t)
        if t < self.t_raetsel:
            self._szene_raetsel(bild, t)
        elif t < self.t_raetsel + self.t_zeit_um:
            self._szene_zeit_um(bild, t - self.t_raetsel)
        else:
            u = t - self.t_raetsel - self.t_zeit_um
            if not self.mit_aufloesung:
                self._szene_ende(bild, u)
            elif u < self.t_pause:
                self._szene_pause(bild, u)
            elif u < self.t_pause + self.t_aufloesung:
                self._szene_aufloesung(bild, u - self.t_pause)
            else:
                self._szene_abschluss(bild, u - self.t_pause - self.t_aufloesung)
        if self.wasserzeichen:
            ebene, pos = self.wasserzeichen
            bild.alpha_composite(ebene, dest=pos)
        rgb = bild.convert("RGB")
        # Loop: die letzten Frames blenden in den ersten über, TikTok spielt dann nahtlos von vorn
        loop_start = self.dauer - self.t_loop
        if self.t_loop > 0 and t > loop_start:
            if self._frame0 is None:
                self._frame0 = self.frame(0.0)
            p = clamp((t - loop_start) / self.t_loop)
            rgb = Image.blend(rgb, self._frame0, p * p * (3 - 2 * p))
        return rgb

    def _ausblenden(self, t, dauer):
        """Faktor für das Ausblenden am Ende einer Szene."""
        if self.t_uebergang <= 0:
            return 1.0
        return clamp((dauer - t) / self.t_uebergang)

    def _partikel(self, bild, t):
        if not self.partikel:
            return
        d = ImageDraw.Draw(bild)
        for x0, y0, tempo, r, staerke, phase in self.partikel:
            y = (y0 - tempo * t) % (self.hoehe + 20) - 10
            x = x0 + 12 * math.sin(t * 0.8 + phase)
            flackern = 0.75 + 0.25 * math.sin(t * 2.3 + phase)
            d.ellipse((x - r, y - r, x + r, y + r), fill=farbmix(self.hintergrund, self.akzent, staerke * flackern))

    def _glow(self, bild, t, mitte_y, deckkraft):
        if self.glow_ebene is None:
            return
        atmen = 0.75 + 0.25 * math.sin(2 * math.pi * t / 2.5)
        einfuegen(bild, self.glow_ebene, (self.mitte_x, mitte_y), deckkraft * atmen)

    def _szene_raetsel(self, bild, t):
        a = self.anim
        raus = self._ausblenden(t, self.t_raetsel)
        c = t - self.t_lesen                       # Sekunden seit Countdown-Start
        rest_sek = self.t_countdown - max(c, 0)
        kritisch = c >= 0 and rest_sek <= self.kritisch_ab
        in_sekunde = max(c, 0) % 1.0
        warn_anteil = clamp((self.kritisch_ab - rest_sek + 0.3) / 0.3) if c >= 0 else 0.0

        if self.vignette is not None and kritisch:
            einfuegen(bild, self.vignette, (self.breite / 2, self.hoehe / 2),
                      (0.35 + 0.65 * (1 - ease_out(in_sekunde / 0.6))) * raus)
        self._glow(bild, t, self.inhalt_y, raus)

        # Alles ist ab dem ersten Frame sichtbar und „zoomt“ kurz heran – das Rätsel selbst ist der Hook
        start_zoom = a.get("einstieg_zoom", 1.0)
        punch = start_zoom + (1 - start_zoom) * ease_out(t / max(0.01, a.get("einstieg_dauer", 0.45)))

        einfuegen(bild, self.label_ebene, (self.mitte_x, self.label_y), raus, punch)
        self._banner(bild, t, raus, punch)

        zoom = punch * (1 + a["zoom_drift"] * t / self.t_raetsel)
        if kritisch:
            zoom *= 1 + 0.02 * (1 - ease_out(in_sekunde / 0.4))  # „Herzschlag“
        einfuegen(bild, self.inhalt_ebene, (self.mitte_x, self.inhalt_y), raus, zoom)

        self._optionen(bild, t, raus, kritisch, in_sekunde)
        self._countdown(bild, c, raus, punch, kritisch, in_sekunde, warn_anteil)

    def _banner(self, bild, t, raus, punch):
        aktiv = [i for i, (start, _) in enumerate(self.banner) if start <= t]
        if not aktiv:
            return
        i = aktiv[-1]
        start, ebene = self.banner[i]
        if i == 0 and start == 0:
            einfuegen(bild, ebene, (self.mitte_x, self.banner_y), raus, punch)
            return
        p = clamp((t - start) / max(0.01, self.anim.get("banner_wechsel", 0.35)))
        if p < 1 and i > 0:  # alter Spruch fliegt nach oben weg
            einfuegen(bild, self.banner[i - 1][1], (self.mitte_x, self.banner_y - 26 * ease_out(p)),
                      (1 - ease_out(p * 1.6)) * raus)
        einfuegen(bild, ebene, (self.mitte_x, self.banner_y + 18 * (1 - ease_out(p))), ease_out(p * 1.4) * raus,
                  0.75 + 0.25 * ease_out_back(p))

    def _optionen(self, bild, t, raus, kritisch, in_sekunde):
        for i, (ebene, warn, (x, y)) in enumerate(self.optionen_ebenen):
            p = ease_out((t - 0.12 - 0.1 * i) / 0.35)
            if p <= 0:
                continue
            y_jetzt = y + 40 * (1 - p)
            einfuegen(bild, ebene, (x, y_jetzt), p * raus)
            if kritisch:  # Rand pulsiert rot im Takt
                einfuegen(bild, warn, (x, y_jetzt), (1 - ease_out(in_sekunde / 0.5)) * raus)

    def _countdown(self, bild, c, raus, punch, kritisch, in_sekunde, warn_anteil):
        a = self.anim
        g = self.cfg["groessen"]
        stil = self.cfg["countdown"].get("stil", "ring")
        rest = clamp(1 - max(c, 0) / self.t_countdown)
        farbe = farbmix(self.akzent, self.warnung, warn_anteil)
        if c < 0:
            return  # Lesephase: noch kein Zeitdruck
        raus *= ease_out(c / 0.2)
        punch = 0.6 + 0.4 * ease_out_back(c / 0.35)
        wackeln = 0.0
        if kritisch:
            wackeln = 9 * math.sin(2 * math.pi * 16 * in_sekunde) * (1 - ease_out(in_sekunde / 0.35))
            self._welle(bild, (self.mitte_x, self.countdown_y), in_sekunde, farbe, raus)
        mitte = (self.mitte_x + wackeln, self.countdown_y)

        if stil == "ring":
            einfuegen(bild, self._ring(rest, farbe), mitte, raus, punch)
        if stil in ("ring", "zahlen", "beides"):
            n = int(clamp(math.ceil(self.t_countdown - math.floor(max(c, 0))), 1, math.ceil(self.t_countdown)))
            puls = 1.0
            if c >= 0:
                puls += a["countdown_puls"] * (1.8 if kritisch else 1.0) * (1 - ease_out(in_sekunde / 0.3))
            ebene = self.zahl_ebenen.get((n, self.warnung if warn_anteil > 0.5 else self.akzent))
            if ebene is not None:
                einfuegen(bild, ebene, mitte, raus, puls * punch)
        if stil in ("balken", "beides"):
            bb, bh = g["countdown_balken_breite"], g["countdown_balken_hoehe"]
            balken = Image.new("RGBA", (bb, bh), (0, 0, 0, 0))
            d = ImageDraw.Draw(balken)
            d.rounded_rectangle((0, 0, bb - 1, bh - 1), radius=bh // 2, fill=self.balken_hg)
            fuell = round(bb * rest)
            if fuell >= bh:
                d.rounded_rectangle((0, 0, fuell - 1, bh - 1), radius=bh // 2, fill=farbe)
            einfuegen(bild, balken, (self.mitte_x, self.balken_y), raus, punch)

    def _ring(self, rest, farbe):
        """Kreisförmiger Timer; doppelt so groß gezeichnet und verkleinert für glatte Kanten."""
        faktor = 2
        d = self.ring_d * faktor
        staerke = round(self.cfg["groessen"].get("countdown_ring_staerke", 18) * self.ring_d / 280) * faktor
        ring = Image.new("RGBA", (d, d), (0, 0, 0, 0))
        zeichnen = ImageDraw.Draw(ring)
        zeichnen.ellipse((0, 0, d - 1, d - 1), outline=self.balken_hg, width=staerke)
        if rest > 0.002:
            ende = -90 + 360 * rest
            zeichnen.arc((0, 0, d - 1, d - 1), start=-90, end=ende, fill=farbe, width=staerke)
            r_mitte = (d - staerke) / 2
            for winkel in (-90, ende):  # abgerundete Enden
                bogen = math.radians(winkel)
                cx = d / 2 + r_mitte * math.cos(bogen)
                cy = d / 2 + r_mitte * math.sin(bogen)
                zeichnen.ellipse((cx - staerke / 2, cy - staerke / 2, cx + staerke / 2, cy + staerke / 2), fill=farbe)
        return ring.resize((self.ring_d, self.ring_d), Image.LANCZOS)

    def _welle(self, bild, mitte, in_sekunde, farbe, raus):
        """Druckwelle, die bei jedem Tick der Schlussphase vom Ring nach außen läuft."""
        p = ease_out(in_sekunde / 0.6)
        if p >= 1:
            return
        faktor = 2
        r = self.ring_d / 2 * (1 + 0.55 * p)
        groesse = math.ceil(2 * r * faktor) + 8
        welle = Image.new("RGBA", (groesse, groesse), (0, 0, 0, 0))
        dicke = max(2, round(6 * faktor * (1 - p)))
        ImageDraw.Draw(welle).ellipse((4, 4, groesse - 5, groesse - 5), outline=farbe[:3] + (255,), width=dicke)
        welle = welle.resize((groesse // faktor, groesse // faktor), Image.LANCZOS)
        einfuegen(bild, welle, mitte, (1 - p) * 0.8 * raus)

    def _szene_zeit_um(self, bild, t):
        if self.vignette is not None:
            einfuegen(bild, self.vignette, (self.breite / 2, self.hoehe / 2), 1 - ease_out(t / 0.7))
        einfuegen(bild, self.inhalt_ebene, (self.mitte_x, self.inhalt_y), 0.12)  # Rätsel bleibt schwach sichtbar
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

        p = t / 0.4
        einfuegen(bild, self.end1_ebene, (self.mitte_x, y + h1 / 2), ease_out(p * 2), 0.7 + 0.3 * ease_out_back(p))
        y += h1 + abstand
        if t > 0.25:  # „Folge …“ springt nach und pulsiert dann sanft weiter
            p = (t - 0.25) / 0.4
            puls = 1 + 0.035 * math.sin(2 * math.pi * max(0.0, t - 0.65) / 0.9)
            einfuegen(bild, self.end2_ebene, (self.mitte_x, y + h2 / 2), ease_out(p * 2),
                      (0.7 + 0.3 * ease_out_back(p)) * puls)
        if self.handle_ebene:
            y += h2 + abstand * 0.6
            einfuegen(bild, self.handle_ebene, (self.mitte_x, y + h3 / 2), ease_out((t - 0.5) / 0.4))


    def _szene_pause(self, bild, t):
        """„Jetzt kommentieren! Auflösung in 3 · 2 · 1“ – damit sich alle vorher festlegen."""
        self._glow(bild, t, self.mitte_y, 0.9)
        raus = self._ausblenden(t, self.t_pause)
        for i, ((ebene, _), y) in enumerate(zip(self.pause_zeilen, self.pause_mitten)):
            p = ease_out((t - 0.08 * i) / 0.3)
            einfuegen(bild, ebene, (self.mitte_x, y + 20 * (1 - p)), p * raus)
        schritt = self.t_pause / 3
        stufe = min(2, int(t / schritt))
        lokal = t - stufe * schritt
        einfuegen(bild, self.pause_zahlen[3 - stufe], (self.mitte_x, self.pause_mitten[-1]),
                  ease_out(lokal / 0.12) * raus, 1.35 - 0.35 * ease_out_back(lokal / 0.3))

    def _szene_aufloesung(self, bild, t):
        raus = self._ausblenden(t, self.t_aufloesung)
        p_label = ease_out(t / 0.25)
        einfuegen(bild, self.loesung_label, (self.mitte_x, self.label_y), p_label * raus,
                  0.8 + 0.2 * ease_out_back(t / 0.35))
        if self.typ == "finde":
            self._glow(bild, t, self.inhalt_y, raus)
            p = ease_out(t / 0.4)
            einfuegen(bild, self.inhalt_ebene, (self.mitte_x, self.inhalt_y), (1 - p) * raus)
            einfuegen(bild, self.finde_aufloesung_ebene, (self.mitte_x, self.inhalt_y), p * raus,
                      1 + 0.04 * (1 - ease_out(t / 0.6)))
            q = (t - 0.3) / 0.35
            if q > 0:
                einfuegen(bild, self.loesung_ebene, (self.mitte_x, self.countdown_y), ease_out(q * 2) * raus,
                          0.8 + 0.2 * ease_out_back(q))
            return
        self._glow(bild, t, self.loesung_y, raus)
        einfuegen(bild, self.kontext_ebene, (self.mitte_x, self.kontext_y), ease_out(t / 0.3) * raus)
        q = (t - 0.15) / 0.35
        if q > 0:  # die Lösung „knallt“ rein
            einfuegen(bild, self.loesung_ebene, (self.mitte_x, self.loesung_y), ease_out(q * 2) * raus,
                      1.4 - 0.4 * ease_out_back(q))
        q = ease_out((t - 0.6) / 0.4)
        einfuegen(bild, self.erklaerung_ebene, (self.mitte_x, self.erklaerung_y + 20 * (1 - q)), q * raus)

    def _szene_abschluss(self, bild, t):
        """„Hattest du's? ✅ oder ❌“ – der einfachste Kommentar überhaupt."""
        self._glow(bild, t, self.mitte_y, ease_out(t / 0.4))
        for i, ((ebene, _), y) in enumerate(zip(self.abschluss_zeilen, self.abschluss_mitten)):
            p = (t - 0.12 * i) / 0.4
            if p > 0:
                einfuegen(bild, ebene, (self.mitte_x, y), ease_out(p * 2), 0.75 + 0.25 * ease_out_back(p))
