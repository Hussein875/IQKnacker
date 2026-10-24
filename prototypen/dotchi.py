"""Prototyp „Dotchi“ – Alltags-Vergleiche als Faktenvideos (1080x1920, 30 fps), mit und ohne Stimme.

Nutzt Schriften und Text-Setzer aus dem IQKnacker-Generator. Aufruf (im IQKnacker-Ordner, venv aktiv):
    python3 prototypen/dotchi.py --stimme <VOICE_ID>            # beide Beispiele mit ElevenLabs-Stimme
    python3 prototypen/dotchi.py --stimme <VOICE_ID> --video kaffee --name anna
Der ElevenLabs-API-Schlüssel steht in ~/.elevenlabs (nur der Schlüssel, nichts sonst) – nie im Repo.
Ohne Schlüssel wird die kostenlose Piper-Test-Stimme benutzt (de-thorsten-low.onnx neben diesem Skript).
Gesprochene Sätze werden in prototypen/.cache zwischengespeichert – erneutes Rendern kostet keine Credits.
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import urllib.error
import urllib.request
import wave

import numpy as np
from PIL import Image, ImageDraw

IQ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, IQ)
from renderer import (TextSetzer, clamp, ease_out, ease_out_back, einfuegen, hex_zu_rgb,  # noqa: E402
                      radialer_verlauf, schrift)
from musik import bass, flaeche, hihat, hz, kick  # noqa: E402

HIER = os.path.dirname(os.path.abspath(__file__))
FETT = f"{IQ}/assets/fonts/Montserrat-ExtraBold.ttf"
NORMAL = f"{IQ}/assets/fonts/Montserrat-Bold.ttf"
EMOJI = f"{IQ}/assets/fonts/NotoColorEmoji.ttf"
STIMME = os.path.join(HIER, "de-thorsten-low.onnx")  # Test-Stimme: github.com/rhasspy/piper/releases/download/v0.0.2/voice-de-thorsten-low.tar.gz
SCHLUESSEL_DATEI = os.path.expanduser("~/.elevenlabs")
CACHE = os.path.join(HIER, ".cache")
ELEVEN = {"stimme": None, "modell": "eleven_multilingual_v2",
          "einstellungen": {"stability": 0.4, "similarity_boost": 0.8, "style": 0.35, "use_speaker_boost": True}}

B, H, FPS, SR = 1080, 1920, 30, 44100
WEISS, GRAU = (255, 255, 255), (170, 172, 185)
ROT, GRUEN, GOLD = hex_zu_rgb("#FF4D6D"), hex_zu_rgb("#2EE59D"), hex_zu_rgb("#FFC83D")
NBSP = " "


def euro(x):
    """1234.5 → „1.234,50 €“, ganze Zahlen ohne Nachkommastellen."""
    if abs(x - round(x)) < 1e-9:
        s = f"{round(x):,}".replace(",", ".")
    else:
        s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + NBSP + "€"


fett = TextSetzer(FETT, EMOJI)
normal = TextSetzer(NORMAL, EMOJI)


def text(t, groesse, farbe=WEISS, akzent=GOLD, breite=900, setzer=fett):
    return setzer.block(t, groesse, breite, farbe, akzent, 1.15)


# ---------------------------------------------------------------- Szenen

class Szene:
    def __init__(self, sprich, **kw):
        self.sprich, self.kw, self.dauer, self.start = sprich, kw, 0.0, 0.0


def zeichne_titel(bild, t, d, kw):
    """Große Zeilen nacheinander, optional mit zweiter Stufe (z. B. Pointe)."""
    zeilen = kw["zeilen"]
    y = kw.get("y", 760)
    for i, (inhalt, groesse) in enumerate(zeilen):
        verz = kw.get("verzoegerung", [0.12 * i] * len(zeilen))[i]
        p = clamp((t - verz) / 0.35)
        if p <= 0:
            y += groesse * 1.3
            continue
        ebene = text(inhalt, groesse)
        einfuegen(bild, ebene, (B / 2, y + ebene.height / 2 + (1 - ease_out(p)) * 40), deckkraft=p,
                  skalierung=0.9 + 0.1 * ease_out_back(p))
        y += ebene.height + 30


def zeichne_zahl(bild, t, d, kw):
    """Überschrift, große hochzählende Zahl, Unterzeile(n)."""
    oben = text(kw["oben"], 64, GRAU)
    einfuegen(bild, oben, (B / 2, 660), deckkraft=clamp(t / 0.25))
    p = ease_out(clamp((t - 0.25) / 1.1))
    zahl = text(euro(round(kw["wert"] * p)), 190, kw.get("farbe", ROT))
    puls = 1 + 0.08 * math.sin(clamp((t - 1.35) / 0.35) * math.pi)
    einfuegen(bild, zahl, (B / 2, 900), deckkraft=clamp((t - 0.2) / 0.2), skalierung=puls)
    y = 1080
    for i, zeile in enumerate(kw.get("unten", [])):
        verz = kw.get("unten_ab", 1.5) + i * 0.9
        q = clamp((t - verz) / 0.3)
        ebene = text(zeile, 70)
        einfuegen(bild, ebene, (B / 2, y + ebene.height / 2 + (1 - ease_out(q)) * 30), deckkraft=q)
        y += ebene.height + 40


def karte(emoji, name, farbe, breite=390):
    ebene = Image.new("RGBA", (breite, 330), (0, 0, 0, 0))
    ImageDraw.Draw(ebene).rounded_rectangle((0, 0, breite - 1, 329), 40, fill=(26, 28, 38, 235),
                                            outline=farbe + (255,), width=5)
    e = text(emoji, 140)
    ebene.alpha_composite(e, ((breite - e.width) // 2, 30))
    n = text(name, 52, breite=breite - 40)
    ebene.alpha_composite(n, ((breite - n.width) // 2, 200))
    return ebene


def zeichne_vs(bild, t, d, kw):
    """Zwei Karten nebeneinander; darunter Preis oder hochzählender Jahreswert mit Balken."""
    links, rechts = kw["links"], kw["rechts"]
    xs = (275, 805)
    einfuegen(bild, text(kw["kopf"], 58, GRAU), (B / 2, 330), deckkraft=clamp(t / 0.25))
    for i, (seite, x) in enumerate(zip((links, rechts), xs)):
        p = clamp((t - 0.1 * i) / 0.35)
        k = karte(seite["emoji"], seite["name"], seite["farbe"])
        einfuegen(bild, k, (x, 590 + (1 - ease_out(p)) * 60), deckkraft=p)
    einfuegen(bild, text("vs.", 70, GOLD), (B / 2, 590), deckkraft=clamp((t - 0.2) / 0.3),
              skalierung=ease_out_back(clamp((t - 0.2) / 0.4)))
    maximal = max(links["wert"], rechts["wert"])
    for i, (seite, x) in enumerate(zip((links, rechts), xs)):
        p = ease_out(clamp((t - 0.45 - 0.15 * i) / 1.2))
        wert = seite["wert"] * p
        if kw.get("balken"):
            hoehe = max(8, round(430 * wert / maximal))
            unten = 1300
            balken = Image.new("RGBA", (220, hoehe), seite["farbe"] + (255,))
            einfuegen(bild, balken, (x, unten - hoehe / 2))
            wert_ebene = text(euro(round(wert)) if p < 1 else euro(seite["wert"]), 76, seite["farbe"])
            einfuegen(bild, wert_ebene, (x, unten - hoehe - 60), deckkraft=clamp(p * 4))
        else:
            wert_ebene = text(euro(seite["wert"]), 96, seite["farbe"])
            einfuegen(bild, wert_ebene, (x, 900), deckkraft=clamp((t - 0.5 - 0.2 * i) / 0.3),
                      skalierung=ease_out_back(clamp((t - 0.5 - 0.2 * i) / 0.4)))
            einfuegen(bild, text(seite.get("einheit", ""), 46, GRAU), (x, 990),
                      deckkraft=clamp((t - 0.6 - 0.2 * i) / 0.3))


def zeichne_liste(bild, t, d, kw):
    """Zeilen erscheinen nacheinander (Rechenweg oder Perspektiven)."""
    if kw.get("kopf"):
        einfuegen(bild, text(kw["kopf"], 60, GRAU), (B / 2, 480), deckkraft=clamp(t / 0.25))
    zeilen = kw["zeilen"]
    abstand = kw.get("abstand", 0.8)
    y = kw.get("y", 620)
    for i, zeile in enumerate(zeilen):
        p = clamp((t - 0.15 - i * abstand) / 0.3)
        groesse = 96 if i == len(zeilen) - 1 and kw.get("letzte_gross") else 78
        ebene = text(zeile, groesse)
        einfuegen(bild, ebene, (B / 2 + (1 - ease_out(p)) * 80, y + ebene.height / 2), deckkraft=p)
        y += ebene.height + 46


ZEICHNER = {"titel": zeichne_titel, "zahl": zeichne_zahl, "vs": zeichne_vs, "liste": zeichne_liste}


# ---------------------------------------------------------------- Video

class Video:
    def __init__(self, name, szenen, fuss, farbe):
        self.name, self.szenen, self.fuss, self.farbe = name, szenen, fuss, farbe
        self.hintergrund = Image.new("RGBA", (B, H), (12, 13, 18, 255))
        self.hintergrund.alpha_composite(radialer_verlauf(B, H, hex_zu_rgb(farbe), 0.28, 0.0, 1.6))
        pille = Image.new("RGBA", (420, 96), (0, 0, 0, 0))
        ImageDraw.Draw(pille).rounded_rectangle((0, 0, 419, 95), 48, fill=GOLD + (255,))
        marke = schrift(FETT, 50)
        ImageDraw.Draw(pille).text((210, 50), "DOTCHI", font=marke, fill=(20, 20, 24), anchor="mm")
        self.marke = pille
        self.fuss_ebene = text(fuss, 34, GRAU, setzer=normal)

    def zeitplan(self, stimm_dauern):
        t = 0.0
        for s, sd in zip(self.szenen, stimm_dauern):
            s.start = t
            s.dauer = max(s.kw.get("min", 2.4), sd + 0.55)
            t += s.dauer
        self.dauer = t + 0.3  # Loop-Überblendung
        return self.dauer

    def frame(self, t):
        bild = self.hintergrund.copy()
        einfuegen(bild, self.marke, (B / 2, 215))
        for s in self.szenen:
            if s.start <= t < s.start + s.dauer:
                lokal = t - s.start
                ebene = Image.new("RGBA", (B, H), (0, 0, 0, 0))
                ZEICHNER[s.kw["typ"]](ebene, lokal, s.dauer, s.kw)
                raus = clamp((lokal - (s.dauer - 0.22)) / 0.22) if s is not self.szenen[-1] else 0
                if raus > 0:
                    ebene.putalpha(ebene.getchannel("A").point(lambda a: int(a * (1 - raus))))
                bild.alpha_composite(ebene)
        einfuegen(bild, self.fuss_ebene, (B / 2, 1470))
        return bild


# ---------------------------------------------------------------- Audio

def elevenlabs(satz):
    """Satz bei ElevenLabs sprechen lassen (MP3, zwischengespeichert) und als 44,1-kHz-Mono-Array zurückgeben."""
    with open(SCHLUESSEL_DATEI, encoding="utf-8") as f:
        schluessel = f.read().strip()
    kennung = json.dumps([ELEVEN["stimme"], ELEVEN["modell"], ELEVEN["einstellungen"], satz], sort_keys=True)
    os.makedirs(CACHE, exist_ok=True)
    mp3 = os.path.join(CACHE, hashlib.sha1(kennung.encode()).hexdigest() + ".mp3")
    if not os.path.exists(mp3):
        anfrage = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN['stimme']}?output_format=mp3_44100_128",
            data=json.dumps({"text": satz, "model_id": ELEVEN["modell"], "voice_settings": ELEVEN["einstellungen"]}).encode(),
            headers={"xi-api-key": schluessel, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        try:
            with urllib.request.urlopen(anfrage, timeout=60) as antwort:
                daten = antwort.read()
        except urllib.error.HTTPError as fehler:
            sys.exit(f"✗ ElevenLabs meldet Fehler {fehler.code}: {fehler.read().decode(errors='replace')[:400]}\n"
                     "  401 = Schlüssel falsch · 402/429 = Kontingent/Tarif · 404/400 = Voice-ID prüfen")
        with open(mp3 + ".tmp", "wb") as f:
            f.write(daten)
        os.replace(mp3 + ".tmp", mp3)
        print(f"  🎙️ gesprochen: {satz[:60]}…")
    roh = subprocess.run([ffmpeg(), "-loglevel", "error", "-i", mp3, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(roh, dtype=np.int16).astype(np.float32) / 32768


def stimme(satz, ziel):
    if ELEVEN["stimme"] and os.path.exists(SCHLUESSEL_DATEI):
        return elevenlabs(satz)
    if ELEVEN["stimme"]:
        sys.exit(f"✗ Kein ElevenLabs-Schlüssel in {SCHLUESSEL_DATEI} gefunden.")
    subprocess.run([sys.executable, "-m", "piper", "-m", STIMME, "-f", ziel], input=satz.encode(),
                   check=True, capture_output=True)
    with wave.open(ziel) as w:
        daten = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        sr = w.getframerate()
    neu = np.interp(np.arange(0, len(daten) * SR / sr) * sr / SR, np.arange(len(daten)), daten)
    return neu


def musik(dauer, rng):
    n = int(dauer * SR)
    spur = np.zeros(n)
    takt = 60 / 100 * 4
    akkorde = [(57, [0, 3, 7, 10]), (53, [0, 4, 7, 11]), (48, [0, 4, 7, 11]), (55, [0, 4, 7, 10])]
    t, i = 0.0, 0
    while t < dauer:
        grund, stufen = akkorde[i % 4]
        stueck = flaeche([hz(grund + 12 + s) for s in stufen], takt, attack=0.3, release=0.6) * 0.22
        tief = bass(hz(grund - 12), takt) * 0.35
        laenge = min(len(stueck), len(tief))
        stueck = stueck[:laenge] + tief[:laenge]
        a = int(t * SR)
        spur[a:a + len(stueck)] += stueck[:n - a]
        for schlag in range(4):
            b = int((t + schlag * takt / 4) * SR)
            k = kick() * 0.55
            spur[b:b + len(k)] += k[:max(0, n - b)]
            hh = hihat(rng) * 0.18
            c = int((t + (schlag + 0.5) * takt / 4) * SR)
            spur[c:c + len(hh)] += hh[:max(0, n - c)]
        t += takt
        i += 1
    return spur


def whoosh(rng, dauer=0.35):
    x = np.arange(int(dauer * SR)) / SR
    rausch = rng.standard_normal(len(x))
    huelle = np.sin(np.pi * x / dauer) ** 2
    gefiltert = np.convolve(rausch, np.ones(12) / 12, mode="same")
    return gefiltert * huelle * 0.5


def ching(dauer=0.6):
    x = np.arange(int(dauer * SR)) / SR
    ton = sum(np.sin(2 * np.pi * f * x) * a for f, a in ((1568, 0.5), (2093, 0.35), (3136, 0.2)))
    return ton * np.exp(-x * 7) * 0.45


def audio(video, mit_stimme, stimmen, ziel):
    rng = np.random.default_rng(7)
    n = int(video.dauer * SR)
    m = musik(video.dauer + 1, rng)[:n]
    sprache = np.zeros(n)
    effekte = np.zeros(n)
    for s, st in zip(video.szenen, stimmen):
        a = int((s.start + 0.15) * SR)
        if mit_stimme:
            sprache[a:a + len(st)] += st[:max(0, n - a)]
        w = whoosh(rng)
        b = int(s.start * SR)
        effekte[b:b + len(w)] += w[:max(0, n - b)]
        if s.kw.get("ching") is not None:
            c = ching()
            b = int((s.start + s.kw["ching"]) * SR)
            effekte[b:b + len(c)] += c[:max(0, n - b)]
    # Musik unter der Stimme leiser (Ducking)
    huelle = np.convolve(np.abs(sprache), np.ones(SR // 10) / (SR // 10), mode="same")
    ducking = 1 - 0.65 * np.clip(huelle * 12, 0, 1)
    mix = m * (ducking if mit_stimme else 1) * (0.55 if mit_stimme else 0.8) + sprache * 1.0 + effekte
    mix = mix / max(1e-6, np.max(np.abs(mix))) * 0.9
    stereo = (np.repeat(mix[:, None], 2, axis=1) * 32767).astype(np.int16)
    with wave.open(ziel, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def rendern(video, ausgabe):
    os.makedirs(ausgabe, exist_ok=True)
    stimmen, dauern = [], []
    for i, s in enumerate(video.szenen):
        st = stimme(s.sprich, os.path.join(ausgabe, f".{video.name}_{i}.wav"))
        stimmen.append(st)
        dauern.append(len(st) / SR)
    video.zeitplan(dauern)
    erster = video.frame(0).convert("RGB")
    erster.save(os.path.join(ausgabe, f"{video.name}.png"))
    frames = int(video.dauer * FPS)
    roh = os.path.join(ausgabe, f".{video.name}.mp4")  # Bild einmal (fast verlustfrei), Ton zweimal dazu
    prozess = subprocess.Popen([ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                "-s", f"{B}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset",
                                "medium", "-crf", "16", "-pix_fmt", "yuv420p", roh], stdin=subprocess.PIPE)
    for i in range(frames):
        t = i / FPS
        bild = video.frame(t).convert("RGB")
        ueber = clamp((t - (video.dauer - 0.3)) / 0.3)
        if ueber > 0:
            bild = Image.blend(bild, erster, ueber)
        prozess.stdin.write(bild.tobytes())
    prozess.stdin.close()
    prozess.wait()
    for mit, endung in ((True, "mit_stimme"), (False, "ohne_stimme")):
        wav = os.path.join(ausgabe, f".{video.name}_{endung}.wav")
        audio(video, mit, stimmen, wav)
        subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", roh, "-i", wav,
                        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", os.path.join(ausgabe, f"{video.name}_{endung}.mp4")],
                       check=True)
        os.remove(wav)
    os.remove(roh)
    for i in range(len(video.szenen)):
        if os.path.exists(os.path.join(ausgabe, f".{video.name}_{i}.wav")):
            os.remove(os.path.join(ausgabe, f".{video.name}_{i}.wav"))
    print(f"✓ {video.name}: {video.dauer:.1f} s")


# ---------------------------------------------------------------- Beispiele

KAFFEE = Video("kaffee", [
    Szene("Kaffee to go oder Kaffee zu Hause? Der Unterschied ist krasser, als du denkst.",
          typ="titel", y=640, zeilen=[("*Kaffee to go* ☕", 110), ("vs.", 80), ("*Zuhause* 🏠", 110),
                                      ("Was kostet dich mehr?", 64)]),
    Szene("Ein Kaffee to go kostet rund drei Euro fünfzig. Zu Hause sind es etwa dreißig Cent.",
          typ="vs", kopf="Pro Kaffee",
          links=dict(emoji="☕", name="To go", farbe=ROT, wert=3.5, einheit="pro Becher"),
          rechts=dict(emoji="🏠", name="Zuhause", farbe=GRUEN, wert=0.3, einheit="pro Tasse")),
    Szene("Jeden Arbeitstag, ein Jahr lang: siebenhundertsiebzig Euro gegen sechsundsechzig.",
          typ="vs", kopf="Pro Jahr · 220 Arbeitstage", balken=True,
          links=dict(emoji="☕", name="To go", farbe=ROT, wert=770),
          rechts=dict(emoji="🏠", name="Zuhause", farbe=GRUEN, wert=66)),
    Szene("Das sind über siebenhundert Euro im Jahr. Und in zehn Jahren mehr als siebentausend.",
          typ="zahl", oben="Unterschied pro Jahr", wert=704, ching=1.35, unten_ab=2.4,
          unten=["In 10 Jahren: *7.040" + NBSP + "€* 😳"], min=4.2),
    Szene("Und was gönnst du dir jeden Tag? Schreib's in die Kommentare!",
          typ="liste", y=620, abstand=0.7, zeilen=["Was gönnst du dir *jeden Tag*? ☕🥐🥤",
                                                    "Schreib's in die Kommentare 👇",
                                                    "Schick das deinem *Kaffee-Junkie* 😏"]),
], fuss="Beispielrechnung · 220 Arbeitstage im Jahr", farbe="#FF4D6D")

DOENER = Video("doener", [
    Szene("Dein Döner kostet dich siebenhundertachtzig Euro. Im Jahr.",
          typ="zahl", oben="Dein Döner 🥙 kostet dich", wert=780, ching=1.35, unten_ab=1.5,
          unten=["… *im Jahr.* 😳"], min=3.0),
    Szene("Zwei Döner pro Woche, je sieben Euro fünfzig, mal zweiundfünfzig Wochen.",
          typ="liste", kopf="So kommt's zustande", abstand=0.75, letzte_gross=True,
          zeilen=["2 Döner pro Woche 🥙🥙", "× 7,50" + NBSP + "€", "× 52 Wochen", "= *780" + NBSP + "€*"]),
    Szene("Das sind fünfundsechzig Euro im Monat. In zehn Jahren siebentausendachthundert Euro. "
          "Oder tausendvierzig Döner.",
          typ="liste", kopf="Das heißt:", abstand=1.6,
          zeilen=["*65" + NBSP + "€* im Monat", "*7.800" + NBSP + "€* in 10 Jahren", "= *1.040 Döner* 🥙"]),
    Szene("Lohnt sich das? Ehrlich gesagt: absolut.",
          typ="titel", y=700, zeilen=[("Lohnt sich das? 🤔", 100), ("*Absolut.* 😋", 130)],
          verzoegerung=[0, 1.3], ching=1.3),
    Szene("Und wie viele sind es bei dir pro Woche? Schreib's in die Kommentare!",
          typ="liste", y=620, abstand=0.7, zeilen=["Wie viele Döner 🥙 isst *du* pro Woche?",
                                                    "Schreib's in die Kommentare 👇",
                                                    "Schick das deinem *Döner-Buddy* 😏"]),
], fuss="Beispielrechnung · 7,50 € pro Döner", farbe="#FFC83D")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dotchi-Prototyp: Beispielvideos rendern")
    parser.add_argument("--stimme", help="ElevenLabs-Voice-ID (ohne: kostenlose Piper-Test-Stimme)")
    parser.add_argument("--modell", default=ELEVEN["modell"], help="ElevenLabs-Modell (Standard: %(default)s)")
    parser.add_argument("--video", choices=["kaffee", "doener", "alle"], default="alle")
    parser.add_argument("--name", help="Zusatz für die Dateinamen, z. B. --name anna → kaffee_anna_mit_stimme.mp4")
    args = parser.parse_args()
    ELEVEN["stimme"], ELEVEN["modell"] = args.stimme, args.modell
    ziel = os.path.join(HIER, "out")
    for v in (KAFFEE, DOENER):
        if args.video in ("alle", v.name):
            if args.name:
                v.name = f"{v.name}_{args.name}"
            rendern(v, ziel)
    print(f"Fertig – Videos in {os.path.relpath(ziel)}")
