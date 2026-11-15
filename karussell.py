"""Foto-Karussells für TikTok und Instagram: mehrere Rätsel zum Durchwischen, Lösungen auf der letzten Folie.

Aufbau: Titelfolie („5 Wort-Rätsel – wie viele schaffst du?“), je Rätsel eine Folie, zum Schluss alle Lösungen
mit der Frage „Wie viele hattest du?“ – das bringt Kommentare. Format 1080 × 1350 (4:5, das höchste Format, das
Instagram im Feed erlaubt; TikTok zeigt es mit Rand), gespeichert als JPEG (TikTok nimmt nur JPEG/WebP).
Gedacht für Rätsel, die schon als Video gelaufen sind – ein „Best of“ in neuem Format.

    python3 karussell.py --name wort_best_of --titel "5 Wort-Rätsel" 64 66 68 67 65
"""

import argparse
import json
import os

from PIL import Image, ImageDraw

from renderer import TextSetzer, einfuegen, einstellungen, hex_zu_rgb, radialer_verlauf

BASIS = os.path.dirname(os.path.abspath(__file__))
B, H = 1080, 1350
ORDNER = "karussell"
HOECHSTENS = 10  # mehr Bilder nimmt die Metricool-CSV nicht: Titel + 8 Rätsel + Lösungen


class Folien:
    def __init__(self, cfg, akzent):
        self.cfg = cfg
        s, f = cfg["schriften"], cfg["farben"]
        self.fett_pfad = os.path.join(BASIS, s["fett"])
        self.fett = TextSetzer(self.fett_pfad, os.path.join(BASIS, s["emoji"]))
        self.normal = TextSetzer(os.path.join(BASIS, s["normal"]), os.path.join(BASIS, s["emoji"]))
        self.weiss = hex_zu_rgb(f["text"]) + (255,)
        self.dezent = hex_zu_rgb(f["dezent"]) + (255,)
        self.dunkel = hex_zu_rgb(f["label_text"]) + (255,)
        self.akzent = hex_zu_rgb(akzent) + (255,)
        self.grund = Image.new("RGBA", (B, H), hex_zu_rgb(f["hintergrund"]) + (255,))
        self.grund.alpha_composite(radialer_verlauf(B, H, self.akzent[:3], 0.22, 0.0, 1.5))
        logo = os.path.join(BASIS, "assets/logo/logo_komplett.png")
        if os.path.exists(logo):
            bild = Image.open(logo).convert("RGBA")
            bild = bild.resize((round(bild.width * 90 / bild.height), 90), Image.LANCZOS)
            einfuegen(self.grund, bild, (B / 2, 95))
        else:
            einfuegen(self.grund, self.normal.block("@iqknacker", 40, 600, self.dezent, self.dezent), (B / 2, 95))

    def pille(self, text, groesse=40):
        """Gefüllte Plakette wie im Video („RÄTSEL 1/5“), Emojis erlaubt."""
        inhalt = self.fett.block(text, groesse, 900, self.dunkel, self.dunkel, 1.0)
        rand_x, rand_y = round(groesse * 0.8), round(groesse * 0.3)
        ebene = Image.new("RGBA", (inhalt.width + 2 * rand_x, inhalt.height + 2 * rand_y), (0, 0, 0, 0))
        ImageDraw.Draw(ebene).rounded_rectangle((0, 0, ebene.width - 1, ebene.height - 1), ebene.height // 2,
                                                fill=self.akzent)
        ebene.alpha_composite(inhalt, dest=(rand_x, rand_y))
        return ebene

    def text(self, t, groesse, farbe=None, breite=920, setzer=None):
        return (setzer or self.fett).block(t, groesse, breite, farbe or self.weiss, self.akzent, 1.18)

    def passend(self, t, max_h, max_groesse, min_groesse=44, breite=920):
        groesse = self.fett.passende_groesse(t, breite, max_h, max_groesse, min_groesse, 1.18)
        return self.text(t, groesse, breite=breite)

    def titel(self, label, titel, unterzeile):
        bild = self.grund.copy()
        einfuegen(bild, self.pille(label), (B / 2, 230))
        einfuegen(bild, self.passend(f"*{titel}*", 330, 130), (B / 2, 560))
        einfuegen(bild, self.text(unterzeile, 64), (B / 2, 800))
        einfuegen(bild, self.text("Erst selbst lösen – Lösungen am Ende!", 40, self.dezent, setzer=self.normal),
                  (B / 2, 960))
        einfuegen(bild, self.pille("Wischen 👉", groesse=44), (B / 2, 1180))
        return bild

    def raetsel(self, nummer, anzahl, frage):
        bild = self.grund.copy()
        einfuegen(bild, self.pille(f"RÄTSEL {nummer}/{anzahl}"), (B / 2, 230))
        einfuegen(bild, self.passend(frage, 760, 96), (B / 2, 700))
        einfuegen(bild, self.text("Antwort merken 🤫  Weiter 👉", 40, self.dezent, setzer=self.normal),
                  (B / 2, 1230))
        return bild

    def loesungen(self, raetsel, frage_ende):
        bild = self.grund.copy()
        einfuegen(bild, self.pille("LÖSUNGEN"), (B / 2, 230))
        zeilen = [self.text(f"*{i}.*  {r['loesung']}", 64 if len(raetsel) <= 6 else 52, breite=940)
                  for i, r in enumerate(raetsel, 1)]
        abstand = 26
        gesamt = sum(z.height for z in zeilen) + abstand * (len(zeilen) - 1)
        y = 700 - gesamt / 2
        for z in zeilen:
            einfuegen(bild, z, (B / 2, y + z.height / 2))
            y += z.height + abstand
        einfuegen(bild, self.text(frage_ende, 52), (B / 2, 1200))
        return bild


def erzeuge(cfg, raetsel, titel, unterzeile, name):
    """Speichert die Folien als JPEG unter output/karussell/<name>_kNN.jpg und gibt die Pfade zurück."""
    raetsel = raetsel[:HOECHSTENS - 2]
    kat = einstellungen(cfg, raetsel[0])
    folien = Folien(cfg, kat.get("akzent") or cfg["farben"]["akzent"])
    label = kat.get("label") or raetsel[0]["kategorie"].upper()
    bilder = [folien.titel(label, titel, unterzeile)]
    bilder += [folien.raetsel(i, len(raetsel), r["frage"]) for i, r in enumerate(raetsel, 1)]
    bilder.append(folien.loesungen(raetsel, f"Wie viele hattest du? *Schreib 0–{len(raetsel)}* 👇"))
    ziel = os.path.join(BASIS, cfg["ausgabe"]["ordner"], ORDNER)
    os.makedirs(ziel, exist_ok=True)
    pfade = []
    for i, bild in enumerate(bilder, 1):
        pfad = os.path.join(ziel, f"{name}_k{i:02d}.jpg")
        bild.convert("RGB").save(pfad, "JPEG", quality=90)
        pfade.append(pfad)
    return pfade


if __name__ == "__main__":
    import generate
    parser = argparse.ArgumentParser(description="Rätsel-Karussell (Foto-Post) erzeugen")
    parser.add_argument("ids", type=int, nargs="+", help="Rätsel-IDs in der gewünschten Reihenfolge")
    parser.add_argument("--name", required=True, help="Dateiname, z. B. wort_best_of")
    parser.add_argument("--titel", required=True, help="z. B. „5 Wort-Rätsel“")
    parser.add_argument("--unterzeile", default="Wie viele schaffst du? 🧠")
    args = parser.parse_args()
    with open(os.path.join(BASIS, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    alle = generate.lade_json(generate.RAETSEL_DATEI) if hasattr(generate, "RAETSEL_DATEI") \
        else generate.lade_json(os.path.join(BASIS, "raetsel.json"))
    alle = alle if isinstance(alle, list) else alle["raetsel"]
    generate.neue_raetsel_laden(alle, cfg)
    nach_id = {r["id"]: r for r in alle}
    pfade = erzeuge(cfg, [nach_id[i] for i in args.ids], args.titel, args.unterzeile, args.name)
    print(f"✓ {len(pfade)} Folien → {os.path.relpath(os.path.dirname(pfade[0]), BASIS)}/{args.name}_k01.jpg …")
