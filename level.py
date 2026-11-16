"""Level-Videos: mehrere kurze Rätsel hintereinander, jedes schwerer – „Wie weit kommst du?“

Ein Eintrag vom Typ `level` enthält unter `level` eine Liste kleiner Rätsel (`frage`, `loesung`, optional
`sekunden`, `sprich`, `sprich_loesung`). Ablauf pro Level: Frage erscheint → kurzer Countdown → die Lösung
springt herein (mit einem Ton, der von Level zu Level höher wird) → nächstes Level. Oben läuft eine
Fortschrittsanzeige mit, die Farbe wandert von Grün (Level 1) nach Rot (letztes Level). Am Ende steht
„Wie weit bist du gekommen? Schreib dein Level“ – der Kommentar schreibt sich von selbst.

Der Renderer hat dieselbe Schnittstelle wie RaetselRenderer (frame, ticks, Zeitpunkte für Musik und Stimme),
damit generate.py, musik.py und die Stimme unverändert damit arbeiten.
"""

import math

from PIL import Image, ImageDraw

from renderer import RaetselRenderer, clamp, ease_out, ease_out_back, einfuegen, hex_zu_rgb, radialer_verlauf

FARBEN = ["#6FCF97", "#B8E986", "#F2C94C", "#F2994A", "#FF5C5C"]   # Level 1 → letztes Level
SEKUNDEN = [3, 4, 5, 6, 7]                                         # Denkzeit je Level (Standard)
SPRUECHE = ["Aufwärmen 😌", "Noch easy 🙂", "Jetzt wird's ernst 😬", "Nur noch wenige dabei 🔥", "Level Genie 🧠"]


class LevelRenderer(RaetselRenderer):
    def __init__(self, config, raetsel, basis_pfad):
        self._basis_einrichten(config, raetsel, basis_pfad)
        z, lv = config["zeiten"], config.get("level", {})
        self.level = raetsel["level"]
        n = len(self.level)
        farben = lv.get("farben", FARBEN)
        self.level_farben = [hex_zu_rgb(farben[round(i * (len(farben) - 1) / max(1, n - 1))]) + (255,)
                             for i in range(n)]
        standard = lv.get("sekunden", SEKUNDEN)
        vorgabe = raetsel.get("_level_zeiten") or []  # mit Stimme: Mindestzeiten, damit jeder Satz hineinpasst
        self.abschnitte, t = [], 0.0                  # je Level: (Start, Denkzeit, Dauer der Auflösung)
        for i, eintrag in enumerate(self.level):
            denkzeit = float(eintrag.get("sekunden") or standard[min(i, len(standard) - 1)])
            aufloesung = float(lv.get("aufloesung", 1.5))
            if i < len(vorgabe):
                denkzeit, aufloesung = max(denkzeit, vorgabe[i][0]), max(aufloesung, vorgabe[i][1])
            self.abschnitte.append((t, denkzeit, aufloesung))
            t += denkzeit + aufloesung
        self.t_raetsel = t                            # Ende des letzten Levels
        self.t_abschluss = lv.get("abschluss", 2.6)
        self.dauer = self.t_raetsel + self.t_abschluss
        self.t_loop = min(z.get("loop", 0), self.t_abschluss)
        self.t_uebergang = z["uebergang"]
        # Werte, die Musik und Soundeffekte erwarten: ein einziger langer „Countdown“ ohne Schlussphase
        self.t_lesen, self.t_countdown, self.t_zeit_um, self.kritisch_ab = 0.0, self.t_raetsel, 0, 0
        self.mit_aufloesung, self.ruhig = False, True
        self.anim = config["animation"]
        self.loesungsfarbe = hex_zu_rgb(config["farben"].get("loesung", "#6FCF97")) + (255,)

        self._layout()
        self.fortschritt_y = self.label_y + 62
        self.spruch_y = self.label_y + 132
        self.frage_oben = self.spruch_y + 56
        self.frage_y = (self.frage_oben + self.bereich_unten) / 2
        self._level_vorbereiten()
        self._wasserzeichen_vorbereiten()
        self._partikel_vorbereiten()
        self._frame0 = None

    # ---- vorbereitete Ebenen
    def _level_vorbereiten(self):
        g = self.cfg["groessen"]
        textbreite = self.inhalt_breite - 20
        n = len(self.level)
        sprueche = self.texte.get("level_sprueche") or SPRUECHE
        hook = self.raetsel.get("hook") or self._text("hook")
        self.ebenen = []
        for i, eintrag in enumerate(self.level):
            farbe = self.level_farben[i]
            frage = str(eintrag["frage"])
            groesse = self.setzer_fett.passende_groesse(frage, textbreite, self.bereich_unten - self.frage_oben - 40,
                                                        g.get("level_frage", 150), g["raetsel_min"], 1.2)
            if i == 0:
                self.raetsel_schriftgroesse = groesse
            spruch = hook if i == 0 and hook else sprueche[round(i * (len(sprueche) - 1) / max(1, n - 1))]
            loesung = str(eintrag["loesung"])
            self.ebenen.append({
                "label": self._pille(f"LEVEL {i + 1}/{n}", farbe),
                "spruch": self._einzeilig(self.setzer_fett, spruch, g.get("level_spruch", 58), textbreite, farbe,
                                          self.textfarbe),
                "frage": self.setzer_fett.block(frage, groesse, textbreite, self.textfarbe, farbe, 1.2),
                "loesung": self._einzeilig(self.setzer_fett, loesung, g.get("level_loesung", 130), textbreite - 130,
                                           self.loesungsfarbe, self.loesungsfarbe, 56),
                "glow": radialer_verlauf(round(self.inhalt_breite * 1.25), round(self.inhalt_breite * 1.25), farbe,
                                         self.anim.get("glow_deckkraft", 0.13), 0.0, 1.4),
                "zahlen": {k: self.setzer_fett.block(str(k), round(g["countdown_zahl"] * self.ring_d / 280), 400,
                                                     farbe, farbe, 1.0)
                           for k in range(1, math.ceil(self.abschnitte[i][1]) + 1)},
            })
        letzte = self.level_farben[-1]
        zeilen = [(self._text("level_abschluss_1") or "Wie weit bist *du* gekommen?", g.get("abschluss_1", 110), 46),
                  (self._text("level_abschluss_2") or "Schreib dein *Level* in die Kommentare 👇",
                   g.get("abschluss_2", 70), 40),
                  (self._text("level_abschluss_3") or f"Alle {n} geschafft? Respekt! 🏆", g.get("abschluss_3", 52), 50)]
        self.abschluss_zeilen = [(self.setzer_fett.block(text.replace("{anzahl}", str(n)), groesse, textbreite,
                                                         self.textfarbe, letzte, 1.15), abstand)
                                 for text, groesse, abstand in zeilen]
        handle = self.texte.get("handle")
        if handle:
            self.abschluss_zeilen.append((self.setzer_normal.block(handle, g["handle"], textbreite, self.dezent,
                                                                   letzte, 1.2), 0))
        self.abschluss_mitten = self._stapel(self.abschluss_zeilen)

    # ---- Zeitpunkte für Ton, Musik und Stimme
    def vorschau_zeitpunkt(self):
        return min(1.2, self.abschnitte[0][1] - 0.3)

    def ticks(self):
        return [(start + k, False) for start, denkzeit, _ in self.abschnitte for k in range(math.ceil(denkzeit))]

    def pause_ticks(self):
        return []

    def aufloesung_zeitpunkt(self):
        return None

    def tipp_zeitpunkt(self):
        return None

    def extra_toene(self):
        """Ein heller Dreiklang pro gelöstem Level – jedes Level einen Ganzton höher: (Zeit, Dauer, Töne, Lautstärke,
        Abklingen). Nach dem letzten Level folgt eine kleine Fanfare."""
        toene = []
        for i, (start, denkzeit, _) in enumerate(self.abschnitte):
            f = 880.0 * 2 ** (2 * i / 12)
            toene.append((start + denkzeit, 0.9, [(f, 1.0), (f * 1.26, 0.6), (f * 1.5, 0.45)], 0.24, 5))
        f = 880.0 * 2 ** (2 * len(self.abschnitte) / 12)
        for k, faktor in enumerate((1.0, 1.26, 1.5, 2.0)):
            toene.append((self.t_raetsel + 0.09 * k, 0.8, [(f * faktor, 1.0)], 0.16, 5))
        return toene

    def stimme_start(self, rolle):
        """Rolle = ("frage", Level-Index) oder ("loesung", Level-Index)."""
        art, i = rolle
        start, denkzeit, _ = self.abschnitte[i]
        return start + 0.1 if art == "frage" else start + denkzeit + 0.1

    # ---- Frames
    def frame(self, t):
        aktuell = max(i for i, (start, _, _) in enumerate(self.abschnitte) if start <= min(t, self.t_raetsel - 1e-6))
        self.akzent = self.level_farben[aktuell]      # färbt die Lichtpunkte im Hintergrund
        bild = Image.new("RGBA", (self.breite, self.hoehe), self.hintergrund)
        self._partikel(bild, t)
        if t < self.t_raetsel:
            self._szene_level(bild, t, aktuell)
        else:
            self._szene_ende(bild, t - self.t_raetsel)
        if self.wasserzeichen:
            ebene, pos = self.wasserzeichen
            bild.alpha_composite(ebene, dest=pos)
        rgb = bild.convert("RGB")
        loop_start = self.dauer - self.t_loop
        if self.t_loop > 0 and t > loop_start:        # nahtloser Loop: die letzten Frames gehen in den ersten über
            if self._frame0 is None:
                self._frame0 = self.frame(0.0)
            p = clamp((t - loop_start) / self.t_loop)
            rgb = Image.blend(rgb, self._frame0, p * p * (3 - 2 * p))
        return rgb

    def _fortschritt(self, bild, aktuell, lokal, geloest):
        n = len(self.level)
        breite, hoehe, abstand = min(96, (self.inhalt_breite - 60) // n - 10), 12, 10
        gesamt = n * breite + (n - 1) * abstand
        leiste = Image.new("RGBA", (gesamt, hoehe), (0, 0, 0, 0))
        d = ImageDraw.Draw(leiste)
        for i in range(n):
            x = i * (breite + abstand)
            fertig = i < aktuell or (i == aktuell and geloest)
            farbe = self.level_farben[i] if fertig else self.balken_hg
            d.rounded_rectangle((x, 0, x + breite - 1, hoehe - 1), radius=hoehe // 2, fill=farbe)
            if i == aktuell and not geloest:          # das laufende Level füllt sich mit der Denkzeit
                anteil = clamp(lokal / self.abschnitte[i][1])
                if anteil * breite >= hoehe:
                    d.rounded_rectangle((x, 0, x + round(breite * anteil) - 1, hoehe - 1), radius=hoehe // 2,
                                        fill=self.level_farben[i])
        einfuegen(bild, leiste, (self.mitte_x, self.fortschritt_y))

    def _szene_level(self, bild, t, i):
        start, denkzeit, aufloesung = self.abschnitte[i]
        lokal = t - start
        e, farbe = self.ebenen[i], self.level_farben[i]
        geloest = lokal >= denkzeit
        # Level 1 steht ab dem ersten Bild da (Hook); die anderen springen mit einem kurzen Zoom herein
        rein = 1.0 if i == 0 else ease_out(lokal / 0.16)
        punch = 1 + (0.06 if i == 0 else 0.14) * (1 - ease_out(lokal / 0.4))
        raus = clamp((denkzeit + aufloesung - lokal) / 0.18) if i < len(self.level) - 1 else \
            clamp((denkzeit + aufloesung - lokal) / max(0.01, self.t_uebergang))
        atmen = 0.75 + 0.25 * math.sin(2 * math.pi * t / 2.5)
        einfuegen(bild, e["glow"], (self.mitte_x, self.frage_y), rein * raus * atmen)
        einfuegen(bild, e["label"], (self.mitte_x, self.label_y), 1.0, 1 + 0.25 * (1 - ease_out(lokal / 0.3)))
        self._fortschritt(bild, i, lokal, geloest)
        einfuegen(bild, e["spruch"], (self.mitte_x, self.spruch_y + 16 * (1 - rein)), rein * raus)
        einfuegen(bild, e["frage"], (self.mitte_x, self.frage_y), rein * raus, punch)
        mitte = (self.mitte_x, self.countdown_y)
        if not geloest:
            rest = clamp(1 - lokal / denkzeit)
            in_sekunde = lokal % 1.0
            einfuegen(bild, self._ring(rest, farbe), mitte, rein, 0.6 + 0.4 * ease_out_back(lokal / 0.3))
            k = int(clamp(math.ceil(denkzeit - math.floor(lokal)), 1, math.ceil(denkzeit)))
            puls = 1 + self.anim["countdown_puls"] * (1 - ease_out(in_sekunde / 0.3))
            einfuegen(bild, e["zahlen"][k], mitte, rein, puls)
        else:  # die Lösung springt an die Stelle des Countdowns, davor ein grüner Haken
            q = (lokal - denkzeit) / 0.3
            loesung = e["loesung"]
            radius = min(48, loesung.height // 2)
            gesamt = Image.new("RGBA", (loesung.width + 2 * radius + 26, max(loesung.height, 2 * radius)), (0, 0, 0, 0))
            self._zeichen(ImageDraw.Draw(gesamt), (radius, gesamt.height / 2), radius, True, self.loesungsfarbe)
            gesamt.alpha_composite(loesung, (2 * radius + 26, (gesamt.height - loesung.height) // 2))
            einfuegen(bild, gesamt, mitte, ease_out(q * 2) * raus, 1.45 - 0.45 * ease_out_back(q))

    def _szene_ende(self, bild, t):
        """„Wie weit bist du gekommen? Schreib dein Level“ – der einfachste Kommentar überhaupt."""
        letzte = len(self.level) - 1
        einfuegen(bild, self.ebenen[letzte]["glow"], (self.mitte_x, self.mitte_y), ease_out(t / 0.4))
        for i, ((ebene, _), y) in enumerate(zip(self.abschluss_zeilen, self.abschluss_mitten)):
            p = (t - 0.12 * i) / 0.4
            if p > 0:
                einfuegen(bild, ebene, (self.mitte_x, y), ease_out(p * 2), 0.75 + 0.25 * ease_out_back(p))
