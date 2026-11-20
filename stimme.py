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
    "fehler": "Eine Zeile ist falsch. Findest du den Fehler?",
}


def ssl_kontext():
    """Zertifikate: in der Cloud gibt SSL_CERT_FILE die Datei vor, sonst kommen sie aus certifi –
    das python.org-Python auf dem Mac bringt keine eigenen mit."""
    vorgabe = os.environ.get("SSL_CERT_FILE")
    if vorgabe and os.path.exists(vorgabe):
        return ssl.create_default_context(cafile=vorgabe)
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


EINER = ["null", "ein", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun", "zehn", "elf", "zwölf",
         "dreizehn", "vierzehn", "fünfzehn", "sechzehn", "siebzehn", "achtzehn", "neunzehn"]
ZEHNER = ["", "", "zwanzig", "dreißig", "vierzig", "fünfzig", "sechzig", "siebzig", "achtzig", "neunzig"]
ZAHL = re.compile(r"\d{1,3}(?:\.\d{3})+(?!\d)|\d+(?:,\d+)?")   # 1.188 · 63 · 0,5
RECHENWOERTER = {"plus", "minus", "mal", "geteilt", "durch", "gleich", "hoch", "von", "und", "prozent"}


def _unter_tausend(n, allein, gross):
    """1…999 in Worten. `allein`: eine 1 am Ende heißt „eins“ (sonst „ein“ wie in „eintausend“);
    `gross`: in großen Zahlen heißt es „einhundert“, sonst nur „hundert“."""
    wort = ""
    if n >= 100:
        wort = (("ein" if gross else "") if n // 100 == 1 else EINER[n // 100]) + "hundert"
        n %= 100
    if n == 0:
        return wort
    if n == 1:
        return wort + ("eins" if allein else "ein")
    if n < 20:
        return wort + EINER[n]
    return wort + (EINER[n % 10] + "und" if n % 10 else "") + ZEHNER[n // 10]


def zahl_in_worten(n):
    """Ganze Zahl als deutsches Zahlwort: 63 → „dreiundsechzig“, 1188 → „eintausendeinhundertachtundachtzig“."""
    if n == 0:
        return "null"
    if n >= 10 ** 9:
        return str(n)
    teile = []
    millionen, rest = divmod(n, 10 ** 6)
    if millionen:
        teile.append("eine Million" if millionen == 1 else zahl_in_worten(millionen) + " Millionen")
    tausender, rest = divmod(rest, 1000)
    wort = _unter_tausend(tausender, False, True) + "tausend" if tausender else ""
    if rest:
        wort += _unter_tausend(rest, True, bool(tausender or millionen))
    if wort:
        teile.append(wort)
    return " ".join(teile)


def deutsch_sichern(text):
    """Sätze, die außer Zahlen nur Rechenwörter enthalten („15!“, „8 plus 7?“), liest eine mehrsprachige Stimme
    leicht auf Englisch vor – ihr fehlt der Hinweis auf die Sprache. Dann die Zahlen als deutsche Wörter schreiben."""
    woerter = re.findall(r"[A-Za-zÄÖÜäöüß]+", text)
    if not re.search(r"\d", text) or any(w.lower() not in RECHENWOERTER for w in woerter):
        return text

    def wort(m):
        roh = m.group()
        if "," in roh:
            ganz, nach = roh.split(",")
            return zahl_in_worten(int(ganz)) + " Komma " + " ".join(zahl_in_worten(int(z)) for z in nach)
        return zahl_in_worten(int(roh.replace(".", "")))

    text = ZAHL.sub(wort, text.replace(" %", " Prozent").replace("%", " Prozent"))
    return text[:1].upper() + text[1:]


def frage_text(r, cfg):
    """Was die Stimme am Anfang sagt. Ein Rätsel kann mit `sprich` einen eigenen Text vorgeben."""
    if r.get("sprich"):
        return r["sprich"]
    if r.get("typ") == "duell":  # „Wer hat recht?“: Frage, dann beide Antworten
        links, rechts = r["links"], r["rechts"]
        frage = _zahlen_sprechbar(_ohne_emojis(str(r["frage"]).replace("*", "")))
        if frage and frage[-1] not in ".?!":
            frage += "?"
        return (f"{frage} {links['name']} sagt: {_zahlen_sprechbar(_ohne_emojis(str(links['sagt'])))}. "
                f"{rechts['name']} sagt: {_zahlen_sprechbar(_ohne_emojis(str(rechts['sagt'])))}. Wer hat recht?")
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
    if r.get("typ") == "duell":
        recht = r.get("recht")
        if recht in ("links", "rechts"):
            return f"{r[recht]['name']} hat recht!"
        return "Beide haben recht!" if recht == "beide" else "Keiner von beiden hat recht!"
    if r.get("typ") == "fehler":
        return f"Der Fehler steckt in Zeile {r.get('fehler_zeile')}!"
    loesung = _ohne_emojis(str(r.get("loesung", ""))).strip()
    if r.get("kategorie") == "wort" and str(r.get("konzept", "")).startswith("wort-dreier"):
        erkl = _ohne_emojis(str(r.get("erklaerung", ""))).strip()
        if 0 < len(erkl) <= 70:
            return f"{loesung}! {erkl}"
    return _zahlen_sprechbar(f"Die Lösung: {loesung}!")


def level_frage_text(eintrag):
    """Was die Stimme zu einem Level sagt: eigener Text (`sprich`) oder die Frage in sprechbarer Form."""
    if eintrag.get("sprich"):
        return eintrag["sprich"]
    satz = _zahlen_sprechbar(_ohne_emojis(str(eintrag["frage"]).replace("*", "").replace("\n", " ")))
    return satz if satz and satz[-1] in ".?!" else satz + "?"


def level_loesung_text(eintrag):
    return eintrag.get("sprich_loesung") or _zahlen_sprechbar(_ohne_emojis(str(eintrag["loesung"]))) + "!"


def _schluessel():
    if not os.path.exists(SCHLUESSEL_DATEI):
        return None
    with open(SCHLUESSEL_DATEI, encoding="utf-8") as f:
        return f.read().strip() or None


def verfuegbar(cfg):
    st = cfg.get("stimme", {})
    return bool(st.get("aktiv")) and _schluessel() is not None


def figur_stimme(cfg, person):
    """Eigene Stimme einer Duell-Figur (`figuren.<name>.stimme` in config.json) oder None."""
    name = str((person or {}).get("name", "")).lower()
    return (cfg.get("figuren", {}).get(name) or {}).get("stimme") or None


def duell_mit_figuren(r, cfg):
    """Duell mit eigenen Stimmen für beide Figuren? Dann sprechen Anna und Ben ihre Antworten selbst."""
    return (r.get("typ") == "duell" and cfg.get("stimme", {}).get("figuren_stimmen", True)
            and bool(figur_stimme(cfg, r.get("links"))) and bool(figur_stimme(cfg, r.get("rechts"))))


def _antwort_sprechbar(person):
    text = person.get("sprich") or _zahlen_sprechbar(_ohne_emojis(str(person.get("sagt", ""))).strip())
    text = re.sub(r"\b1 h\b", "eine Stunde", text)
    text = re.sub(r"(\d) h\b", r"\1 Stunden", re.sub(r"(\d) min\b", r"\1 Minuten", text))
    return text if text[-1:] in ".?!" else text + "!"


def duell_frage_teile(r, cfg):
    """Duell mit Figuren-Stimmen: [(voice_id oder None = Erzähler, Satz)] – Frage, Anna, Ben, „Wer hat recht?“."""
    links, rechts = r["links"], r["rechts"]
    frage = r.get("sprich_frage")
    if not frage and r.get("sprich"):  # vorhandenes `sprich` bis vor „Anna sagt …“ verwenden
        frage = re.split(rf"\s*{re.escape(str(links.get('name', '')))} sagt", r["sprich"])[0].strip()
    if not frage:
        frage = _zahlen_sprechbar(_ohne_emojis(str(r["frage"]).replace("*", ""))).strip()
    if frage[-1:] not in ".?!":
        frage += "?"
    return [(None, frage), (figur_stimme(cfg, links), _antwort_sprechbar(links)),
            (figur_stimme(cfg, rechts), _antwort_sprechbar(rechts)), (None, "Wer hat recht?")]


def duell_jubel(r, cfg, zufall):
    """Kurzer Jubel der Figur(en), die recht haben – (voice_id, Satz) oder []."""
    saetze = cfg.get("stimme", {}).get("jubel") or ["Ja! Wusste ich's doch!", "Yes! Ich hatte recht!"]
    recht = r.get("recht")
    seiten = ["links", "rechts"] if recht == "beide" else [recht] if recht in ("links", "rechts") else []
    return [(figur_stimme(cfg, r[s]), zufall.choice(saetze)) for s in seiten][:1] if seiten else []


def abschluss_text(r, cfg, zufall):
    """Gesprochener Kommentar-Aufruf am Ende (`stimme.abschluss` in config.json, je Format/Kategorie)."""
    texte = cfg.get("stimme", {}).get("abschluss") or {}
    if not texte:
        return None
    auswahl = texte.get(r.get("typ") or "") or texte.get(r.get("kategorie") or "") or texte.get("standard")
    if not auswahl:
        return None
    satz = zufall.choice(auswahl) if isinstance(auswahl, list) else auswahl
    for seite in ("links", "rechts"):
        if isinstance(r.get(seite), dict):
            satz = satz.replace("{" + seite + "}", str(r[seite].get("name", "")))
    return satz


def sprich(satz, cfg, cache, voice_id=None):
    """Satz bei ElevenLabs sprechen lassen (MP3, zwischengespeichert). Rückgabe: Pfad oder None bei Fehler.
    `voice_id`: andere Stimme als die Erzählerin (z. B. Anna oder Ben im Duell)."""
    satz = deutsch_sichern(satz)
    st = dict(cfg["stimme"])
    if voice_id:
        st["voice_id"] = voice_id
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
