# IQKnacker – Video-Generator

Erzeugt aus einer Rätsel-Liste (`raetsel.json`) automatisch fertige Hochformat-Videos für TikTok, Reels und Shorts – ohne Stimme, nur Text, Grafik und (optional) Musik.

**Ablauf jedes Videos (1080 × 1920, 30 fps, H.264, 11 Sekunden):**

| Abschnitt | Dauer | Inhalt |
|---|---|---|
| Hook | 1,5 s | „Kannst du das lösen?“ – eingeblendet mit leichtem Zoom |
| Rätsel | 7,5 s | Kategorie-Label oben, Rätseltext mittig; nach 2,5 s Lesezeit Countdown 5 → 1 (Zahl + Balken) |
| Endkarte | 2 s | „Schreib deine Lösung in die Kommentare 👇“ + „Folge für die Auflösung“ |

Die Lösung erscheint **nie** im Video – sie landet nur in der Kommentar-Datei zum Anpinnen.

---

## Installation

Voraussetzung: **Python 3.8 oder neuer** ([python.org](https://www.python.org/downloads/)).

```bash
pip install -r requirements.txt
python generate.py --check
```

`--check` zeigt, ob Python, Pillow, FFmpeg, Schriften, Musik und Logo gefunden werden. Fehlende Python-Pakete installiert das Skript beim ersten Start auch selbst.

**FFmpeg:** Ist FFmpeg auf dem Rechner installiert, wird es benutzt. Sonst nimmt das Skript automatisch die FFmpeg-Version aus dem Paket `imageio-ffmpeg` (wird über `requirements.txt` mitinstalliert) – du musst also nichts extra installieren.

---

## Benutzung

```bash
python generate.py              # alle Rätsel mit Status "neu"
python generate.py --id 5       # nur Rätsel 5 (egal welcher Status)
python generate.py --id 3 7 9   # mehrere bestimmte Rätsel
python generate.py --alle       # alle Rätsel (neu) erzeugen
python generate.py --vorschau   # nur Vorschaubilder, schnell zum Kontrollieren
python generate.py --ohne-musik # Videos ohne Musik
python generate.py --liste      # Übersicht aller Rätsel mit Status
```

### Was im Ordner `output/` entsteht (Beispiel Rätsel 5)

| Datei | Inhalt |
|---|---|
| `005_iq.mp4` | das fertige Video |
| `005_iq.png` | Vorschaubild des Rätsel-Frames zur schnellen Kontrolle |
| `005_iq_caption.txt` | Caption + 7 Hashtags zum Reinkopieren |
| `005_iq_kommentar.txt` | Auflösungs-Kommentar zum späteren Anpinnen |

Nach einem erfolgreichen Video wird der Status in `raetsel.json` von `neu` auf `erstellt` gesetzt. Auf `gepostet` setzt du ihn selbst, wenn das Video online ist.

> Das Skript warnt, wenn ein Auflösungs-Kommentar länger als 150 Zeichen ist (TikTok-Limit). Dann einfach die `erklaerung` kürzen.

---

## Neue Rätsel hinzufügen

Öffne `raetsel.json` und hänge einen Eintrag an (Komma zwischen den Einträgen nicht vergessen):

```json
{
  "id": 11,
  "kategorie": "iq",
  "frage": "Was wird nasser, je mehr es trocknet?",
  "loesung": "Ein Handtuch",
  "erklaerung": "Ein Handtuch nimmt beim Abtrocknen das Wasser auf.",
  "schwierigkeit": "leicht",
  "status": "neu"
}
```

| Feld | Bedeutung |
|---|---|
| `id` | eindeutige Nummer, bestimmt den Dateinamen (`011_iq.mp4`) |
| `kategorie` | `iq`, `wissen`, `mathe`, `bild` – oder eine neue (siehe unten) |
| `frage` | Rätseltext. Wird automatisch umbrochen und in der Größe angepasst |
| `loesung` | kommt nur in die Kommentar-Datei, nie ins Video |
| `erklaerung` | kurze Begründung für den Kommentar |
| `schwierigkeit` | `leicht`, `mittel`, `schwer` (zur eigenen Planung) |
| `status` | `neu` → `erstellt` → `gepostet` |
| `bild` *(optional)* | Pfad zu einem Bild, z. B. `"assets/bilder/011.png"` – wird über dem Text angezeigt (für Bildrätsel) |

**Tipps für den Rätseltext:**

- `*Sternchen*` um Wörter setzen → erscheinen in der Akzentfarbe: `"Wie viele *Dreiecke* siehst du?"`
- `\n` erzwingt einen Zeilenumbruch: `"Welche Zahl kommt als Nächstes?\n2 – 6 – 12 – ?"`
- Damit eine Zahlenreihe nicht mitten drin umbricht, statt normaler Leerzeichen geschützte Leerzeichen verwenden (` `), wie in Rätsel 6.
- Kürzere Texte werden größer dargestellt. Ideal sind 1–3 kurze Sätze.

Danach `python generate.py --vorschau` ausführen und die PNGs in `output/` anschauen.

### Neue Kategorie anlegen

In `config.json` unter `kategorien` einen Block ergänzen:

```json
"geschichte": {
  "label": "GESCHICHTE",
  "akzent": "#EB5757",
  "hashtags": ["#geschichte", "#quiz", "#wissen", "#allgemeinwissen", "#history"],
  "captions": ["Weißt du's? 🤔", "Geschichts-Check! 🧠"]
}
```

- `label` – Text der kleinen Plakette oben im Video
- `akzent` *(optional)* – eigene Akzentfarbe für diese Kategorie; ohne Angabe gilt das IQKnacker-Gelb
- `hashtags` – Pool, aus dem pro Video passend ausgewählt wird (zusätzlich zu `hashtags_allgemein`)
- `captions` – Caption-Sätze, pro Rätsel wird einer ausgewählt (immer derselbe für dieselbe ID)

---

## Design ändern

Alles steht zentral in **`config.json`**:

| Bereich | Was du dort einstellst |
|---|---|
| `farben` | Hintergrund, Text, Akzent (`#F2C94C`), Label-Schrift, Balken |
| `schriften` | Pfade zu den Schriftdateien (`.ttf`) |
| `groessen` | Schriftgrößen für Hook, Label, Rätsel (max/min), Countdown, Endkarte |
| `zeiten` | Dauer von Hook, Lesezeit, Countdown, Endkarte, Übergängen (in Sekunden) |
| `animation` | Einblend-Dauer, Start-Zoom, langsamer Zoom, Puls der Countdown-Zahl |
| `countdown.stil` | `"beides"`, `"zahlen"` oder `"balken"` |
| `texte` | Hook-Text, Endkarten-Texte, Handle (`*Sternchen*` = Akzentfarbe) |
| `wasserzeichen` | Logo-Datei, Position (`oben_links`, `oben_rechts`, `unten_links`, `unten_rechts`), Höhe, Deckkraft |
| `safe_zone` | freie Ränder für die TikTok-Oberfläche (oben 150, unten 400, rechts 150 px) |
| `musik` | Ordner, Lautstärke, Ein-/Ausblenden |
| `hashtags_allgemein`, `hashtags_anzahl` | immer verwendete Hashtags, Anzahl insgesamt (5–8) |
| `kommentar_vorlage` | Aufbau des Auflösungs-Kommentars (`{loesung}`, `{erklaerung}`, …) |

**Andere Schrift:** `.ttf` von [Google Fonts](https://fonts.google.com) herunterladen (z. B. *Anton*), in `assets/fonts/` legen und in `config.json` unter `schriften.fett` eintragen.

**Tipp:** Nach jeder Design-Änderung `python generate.py --id 1 --vorschau` – das dauert nur eine Sekunde.

---

## Logo & Musik

- **Logo:** `assets/logo/logo_symbol.png` (PNG mit transparentem Hintergrund). Wird klein als Wasserzeichen oben links eingeblendet. Solange keine Datei da ist, steht dort `@iqknacker` als Text. Anderer Dateiname → `wasserzeichen.datei` in `config.json` anpassen.
- **Musik:** MP3s (auch M4A/WAV/OGG) in `assets/music/` legen. Pro Video wird zufällig ein Track gewählt, auf Videolänge geschnitten (kurze Tracks werden wiederholt) und am Ende ausgeblendet. Ohne Dateien entsteht ein stilles Video (mit leerer Tonspur, damit du in der App einen Sound darunterlegen kannst).

---

## Ordnerstruktur

```
IQKnacker/
├── generate.py        # Kommandozeile, Daten, Captions, FFmpeg
├── renderer.py        # Frames & Animationen (Pillow)
├── config.json        # Design, Zeiten, Texte, Kategorien
├── raetsel.json       # deine Rätsel
├── requirements.txt
├── assets/
│   ├── fonts/         # Montserrat ExtraBold/Bold + Emoji-Schrift
│   ├── logo/          # dein Logo
│   └── music/         # deine Tracks
└── output/            # fertige Videos, Vorschaubilder, Texte
```

Schriften: Montserrat und Noto Color Emoji stehen unter der SIL Open Font License 1.1 (siehe `assets/fonts/LIZENZ.txt`).
