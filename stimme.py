"""Sprecherstimme für IQKnacker-Videos (ElevenLabs, zwischengespeichert).

Die Stimme liest am Anfang die Frage vor und sagt bei der Auflösung die Lösung. Das gibt den ersten
Sekunden Bewegung (man hört sofort, worum es geht) und macht den Kanal persönlicher.

Fehlt der Schlüssel oder antwortet ElevenLabs nicht, entsteht das Video einfach ohne Stimme – der
Wochenlauf am Mac bricht deswegen nie ab.
"""

import hashlib
import json
import os
import re
import ssl
import subprocess
import urllib.error
import urllib.request

SCHLUESSEL_DATEI = os.path.expanduser("~/.elevenlabs")
SR = 44100
_gesperrt = None  # nach einem harten Fehler (Schlüssel, Kontingent, kein Netz) nicht bei jedem Video neu versuchen

# Sätze für Rätsel, deren Text man nicht vorlesen kann (Emojis, Suchbilder)
FESTE_SAETZE = {
    "emoji": "Welche Zahl gehört ans Fragezeichen?",
    "finde": "Findest du das eine Zeichen, das anders ist?",
    "bild": "Schau genau hin!",
}


def ssl_kontext():
    """Zertifikate aus certifi – das python.org-Python auf dem Mac bringt keine eigenen mit."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _ohne_emojis(text):
    return "".join(z for z in text if ord(z) < 0x2190 or z in "×−…–„“‚‘")


def _wort_teil(zeile):
    """„GLÜH___“ → „Glüh“, „___LIFT“ → „Lift“ (Großbuchstaben würde die Stimme sonst buchstabieren)."""
    teil = zeile.replace("_", "").strip()
    return teil.capitalize() if teil.isupper() else teil


def _zahlen_sprechbar(text):
    text = re.sub(r"\s*=\s*\?", "?", text)                 # „65 × 65 = ?“ → „65 × 65?“
    text = text.replace("×", " mal ").replace("−", " minus ").replace("+", " plus ").replace("=", " gleich ")
    text = re.sub(r"(\d)\s*:\s*(\d)", r"\1 geteilt durch \2", text)
    text = text.replace("½", " ein halb ").replace("km/h", "Kilometer pro Stunde").replace("m/s", "Meter pro Sekunde")
    return re.sub(r"\s+", " ", text).strip()


def frage_text(r, cfg):
    """Was die Stimme am Anfang sagt. Ein Rätsel kann mit `sprich` einen eigenen Text vorgeben."""
    if r.get("sprich"):
        return r["sprich"]
    feste = {**FESTE_SAETZE, **cfg.get("stimme", {}).get("feste_saetze", {})}
    if r.get("kategorie") in feste or r.get("typ") in feste:
        return feste.get(r.get("typ")) or feste[r["kategorie"]]
    zeilen = [z.strip() for z in str(r["frage"]).replace("*", "").split("\n") if z.strip()]
    satz = ""
    for z in zeilen:
        if "___" in z:  # Wort-Dreier: jedes Wort als eigener kurzer Satz, dann macht die Stimme Pausen
            z = _wort_teil(z) + "."
        if satz and satz[-1] not in ".?!:" and z[:1].isupper():
            satz += "."
        satz += (" " if satz else "") + z
    if satz and satz[-1] not in ".?!…":
        satz += "?"
    return _zahlen_sprechbar(_ohne_emojis(satz))


def loesung_text(r, cfg):
    """Was die Stimme bei der Auflösung sagt – kurz, damit man die Erklärung selbst liest."""
    if r.get("sprich_loesung"):
        return r["sprich_loesung"]
    loesung = _ohne_emojis(str(r.get("loesung", ""))).strip()
    if r.get("kategorie") == "wort" and str(r.get("konzept", "")).startswith("wort-dreier"):
        erkl = _ohne_emojis(str(r.get("erklaerung", ""))).strip()
        if 0 < len(erkl) <= 70:
            return f"{loesung}! {erkl}"
    return _zahlen_sprechbar(f"Die Lösung: {loesung}!")


def _schluessel():
    if not os.path.exists(SCHLUESSEL_DATEI):
        return None
    with open(SCHLUESSEL_DATEI, encoding="utf-8") as f:
        return f.read().strip() or None


def verfuegbar(cfg):
    st = cfg.get("stimme", {})
    return bool(st.get("aktiv")) and _schluessel() is not None


def sprich(satz, cfg, cache):
    """Satz bei ElevenLabs sprechen lassen (MP3, zwischengespeichert). Rückgabe: Pfad oder None bei Fehler."""
    st = cfg["stimme"]
    kennung = json.dumps([st["voice_id"], st["modell"], st["einstellungen"], satz], sort_keys=True)
    os.makedirs(cache, exist_ok=True)
    mp3 = os.path.join(cache, hashlib.sha1(kennung.encode()).hexdigest() + ".mp3")
    if os.path.exists(mp3):
        return mp3
    global _gesperrt
    if _gesperrt:
        return None
    schluessel = _schluessel()
    if not schluessel:
        print(f"  ⚠ Keine Stimme: kein ElevenLabs-Schlüssel in {SCHLUESSEL_DATEI} – Video ohne Stimme")
        return None
    anfrage = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{st['voice_id']}?output_format=mp3_44100_128",
        data=json.dumps({"text": satz, "model_id": st["modell"],
                         "voice_settings": st["einstellungen"]}).encode(),
        headers={"xi-api-key": schluessel, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    try:
        with urllib.request.urlopen(anfrage, timeout=60, context=ssl_kontext()) as antwort:
            daten = antwort.read()
    except urllib.error.HTTPError as fehler:
        if fehler.code in (401, 402, 403, 429):
            _gesperrt = f"Fehler {fehler.code}"
        print(f"  ⚠ Keine Stimme: ElevenLabs meldet Fehler {fehler.code} "
              f"({fehler.read().decode(errors='replace')[:200]}) – Video ohne Stimme. "
              "401 = Schlüssel falsch · 402/429 = Kontingent/Tarif · 400/404 = Voice-ID/Modell prüfen")
        return None
    except (urllib.error.URLError, OSError) as fehler:
        _gesperrt = "keine Verbindung"
        print(f"  ⚠ Keine Stimme: keine Verbindung zu ElevenLabs ({fehler}) – Video ohne Stimme")
        return None
    if len(daten) < 1000:
        print("  ⚠ Keine Stimme: ElevenLabs hat keine Audiodaten geliefert – Video ohne Stimme")
        return None
    with open(mp3 + ".tmp", "wb") as f:
        f.write(daten)
    os.replace(mp3 + ".tmp", mp3)
    print(f"    🎙️ {satz[:70]}")
    return mp3


def als_samples(ffmpeg, mp3):
    """MP3 → Liste von Float-Samples (Mono, 44,1 kHz). None, wenn das Dekodieren scheitert."""
    import array
    try:
        roh = subprocess.run([ffmpeg, "-loglevel", "error", "-i", mp3, "-ac", "1", "-ar", str(SR),
                              "-f", "s16le", "-"], check=True, capture_output=True).stdout
    except (subprocess.CalledProcessError, OSError):
        return None
    werte = array.array("h")
    werte.frombytes(roh[: len(roh) // 2 * 2])
    return werte


def dauer(samples):
    return len(samples) / SR if samples is not None else 0.0
