# IQKnacker – Video-Generator

Erzeugt aus einer Rätsel-Liste (`raetsel.json`) automatisch fertige Hochformat-Videos für TikTok, Reels und Shorts – ohne Stimme, mit Text, Grafik, Musik und Soundeffekten.

**Ablauf jedes Videos (1080 × 1920, 30 fps, H.264, ca. 15–28 Sekunden – im Schnitt 18 s leicht, 21 s mittel, 24 s schwer):**

| Abschnitt | Dauer | Inhalt |
|---|---|---|
| Lesen | je nach Textlänge | Das Rätsel ist **sofort** zu sehen und zoomt kurz heran, darüber ein Spruch passend zur Schwierigkeit („Die meisten liegen hier falsch 🤯“). Noch **kein Countdown** – erst in Ruhe lesen (ca. 14 Zeichen pro Sekunde, 1,5–10 s). |
| Denkzeit | 5 / 7 / 10 s | Der Ring-Countdown erscheint, Ticken und Beat setzen ein – **leicht 5 s, mittel 7 s, schwer 10 s**. Zwischendurch wechselt der Spruch („Nicht raten – denken! 🧠“) oder ein **Tipp** erscheint. |
| Schlussphase | letzte 2–3 s | Ring wird rot, Zahl wackelt, Druckwellen, roter Rand, Musik doppelt so schnell, Spruch „Jetzt wird's knapp! 😬“ |
| Zeit um! | 0,7 s | „⏱️ ZEIT UM!“ mit rotem Blitz, Einschlag und Gong |
| Kommentar-Pause | 2,1 s | „**Jetzt kommentieren!** Deine Antwort in die Kommentare 👇 – Auflösung in 3 · 2 · 1“ |
| Auflösung | 3,5–8 s | Grünes „AUFLÖSUNG“, die Lösung groß, darunter die Erklärung (so lange, dass man sie lesen kann). Bei Suchrätseln wird das gesuchte Zeichen eingekreist. |
| Abschluss | 2,2 s | „Hattest du's? Schreib ✅ oder ❌ in die Kommentare 👇 – Und bei welcher Sekunde? ⏱️“ – blendet dann in den ersten Frame über, damit das Video **nahtlos loopt** |

Es werden **keine Antworten vorgegeben**: Die Zuschauer sollen rätseln, nicht raten. Mit `--ohne-aufloesung` entstehen Videos ohne Lösung (stattdessen eine Endkarte „📌 Die erste richtige Antwort wird angepinnt“) – praktisch, um beide Varianten zu vergleichen.

---

## Installation

Voraussetzung: **Python 3.8 oder neuer** ([python.org](https://www.python.org/downloads/)).

```bash
pip install -r requirements.txt
python generate.py --check
```

`--check` zeigt, ob Python, Pillow, numpy, FFmpeg, Schriften, Musik und Logo gefunden werden. Fehlende Python-Pakete installiert das Skript beim ersten Start auch selbst.

**FFmpeg:** Ist FFmpeg auf dem Rechner installiert, wird es benutzt. Sonst nimmt das Skript automatisch die FFmpeg-Version aus dem Paket `imageio-ffmpeg` (wird über `requirements.txt` mitinstalliert) – du musst also nichts extra installieren.

---

## Benutzung

```bash
python generate.py                # alle Rätsel mit Status "neu"
python generate.py --id 5         # nur Rätsel 5 (egal welcher Status)
python generate.py --id 3 7 9     # mehrere bestimmte Rätsel
python generate.py --alle         # alle Rätsel erzeugen
python generate.py --vorschau     # nur Vorschaubilder, schnell zum Kontrollieren
python generate.py --ohne-musik   # Videos ohne Musik (z. B. für Trend-Sounds in der App)
python generate.py --ohne-effekte # ohne Ticken, Tipp-Pling und Gong
python generate.py --ohne-aufloesung # Lösung nicht im Video zeigen (Vergleichs-Variante)
python generate.py --liste        # Übersicht aller Rätsel mit Status
python generate.py --plan 7       # Posting-Plan für eine Woche (siehe unten)
```

### Rätsel automatisch erzeugen lassen

Zwei Rätselarten kann das Skript selbst bauen – die Lösung rechnet es dabei selbst aus, sie stimmt also garantiert:

```bash
python generate.py --neu-emoji 5                       # 5 Emoji-Gleichungen (gemischte Schwierigkeit)
python generate.py --neu-finde 5                       # 5 „Finde die 9“-Suchrätsel
python generate.py --neu-emoji 3 --schwierigkeit schwer
```

- **Emoji-Gleichungen** (`🍎 + 🍎 = 4 …`): Bei *mittel* wird multipliziert, bei *schwer* muss man in den Hinweisen teilen und in der Frage an Punkt vor Strich denken – wer stur von links rechnet, liegt falsch. Das sorgt für Diskussionen in den Kommentaren.
- **Finde die 9:** Ein Gitter aus gleichen Zeichen mit genau einem abweichenden (je schwerer, desto größer das Gitter und desto ähnlicher die Zeichen). Reihen und Spalten sind nummeriert; in der Auflösung wird das Zeichen eingekreist.

Die neuen Rätsel landen mit Status `neu` in `raetsel.json`. Danach wie gewohnt `python generate.py`.

### Was im Ordner `output/` entsteht (Beispiel Rätsel 5)

| Datei | Inhalt |
|---|---|
| `005_iq.mp4` | das fertige Video |
| `005_iq.png` | Vorschaubild des Rätsels (auch als TikTok-Titelbild geeignet) |
| `005_iq_aufloesung.png` | Vorschaubild der Auflösung – zum Kontrollieren von Lösung und Erklärung |
| `005_iq_caption.txt` | Caption + 7 Hashtags zum Reinkopieren |
| `005_iq_kommentar.txt` | Kommentar zum Anpinnen („Hattest du's? ✅ oder ❌ …“ mit der Lösung) |

Nach einem erfolgreichen Video wird der Status in `raetsel.json` von `neu` auf `erstellt` gesetzt. Auf `gepostet` setzt du ihn selbst, wenn das Video online ist.

**Reihenfolge:** `python generate.py` arbeitet die Rätsel in der Reihenfolge der Datei ab. Sie ist so sortiert, dass sich leicht, mittel und schwer abwechseln und nie zwei gleiche Kategorien hintereinander kommen – am besten in dieser Reihenfolge posten.

### Posting-Plan

```bash
python generate.py --plan 7                          # 7 Tage, 3 Videos pro Tag (12:30, 18:30, 21:00)
python generate.py --plan 7 --uhrzeiten 12:30,19:00  # eigene Uhrzeiten
python generate.py --plan 7 --start 2026-11-02       # ab einem bestimmten Tag
```

Verteilt alle fertigen, noch nicht geposteten Videos (in der Reihenfolge der Datei) auf Tage und Uhrzeiten und schreibt sie mit Caption und Kommentar in `output/postingplan.txt`. Damit planst du in **TikTok Studio** am Rechner (tiktok.com/tiktokstudio → Hochladen → „Planen“) eine ganze Woche in einem Rutsch ein.

---

## Kommentare anheizen

Das Video fordert zweimal zum Kommentieren auf: **vor der Auflösung** („Jetzt kommentieren!“ – wer sich vorher festlegt, will danach wissen, ob er recht hatte) und **danach** („Hattest du's? ✅ oder ❌ – und bei welcher Sekunde?“). Ein ✅ ist der einfachste Kommentar überhaupt, und mit der Sekunde können die Leute angeben. Bei Fallen-Rätseln diskutieren sie außerdem, ob die Lösung stimmt („Warum 11 und nicht 16?“).

1. **Direkt nach dem Posten:** den Text aus `xxx_kommentar.txt` als eigenen Kommentar posten und **anpinnen**.
2. **Erste Stunde:** auf Kommentare antworten – jede Antwort von dir zählt als weiterer Kommentar:
   - auf ✅ mit Sekunde: „Krass schnell 🔥“ · „Respekt! 🧠“
   - auf ❌: „Nächstes Mal klappt's 💪“ · „Die war auch fies 😅“
   - auf Diskussionen über die Lösung: kurz den Rechenweg erklären – und die Diskussion laufen lassen
3. **Falls die Vergleichs-Variante ohne Auflösung läuft** (`--ohne-aufloesung`): nach 3–6 Stunden die früheste richtige Antwort anpinnen (im Posteingang unter „Kommentare“ nach Zeit sortiert) und mit der Lösung antworten – so verspricht es die Endkarte.

> Das Skript warnt, wenn ein Kommentar länger als 150 Zeichen ist (TikTok-Limit, Emojis zählen doppelt).

---

## Neue Rätsel von Hand hinzufügen

Öffne `raetsel.json` und hänge einen Eintrag an (Komma zwischen den Einträgen nicht vergessen):

```json
{
  "id": 100,
  "kategorie": "iq",
  "frage": "Eine Uhr schlägt um 6 Uhr sechsmal – das dauert 5 Sekunden. Wie lange dauern 12 Schläge um 12 Uhr?",
  "loesung": "11 Sekunden",
  "erklaerung": "6 Schläge = 5 Pausen à 1 s. 12 Schläge = 11 Pausen = 11 Sekunden.",
  "schwierigkeit": "mittel",
  "status": "neu"
}
```

| Feld | Bedeutung |
|---|---|
| `id` | eindeutige Nummer, bestimmt den Dateinamen (`100_iq.mp4`) |
| `kategorie` | `iq`, `wissen`, `mathe`, `wort`, `emoji`, `finde`, `bild` – oder eine neue (siehe unten) |
| `frage` | Rätseltext. Wird automatisch umbrochen und in der Größe angepasst |
| `loesung` | kommt nur in die Kommentar-Datei, nie ins Video |
| `erklaerung` | kurze Begründung für den Kommentar |
| `schwierigkeit` | `leicht`, `mittel`, `schwer` – bestimmt die Zeit (5 / 7 / 10 s) und welcher Spruch oben erscheint |
| `status` | `neu` → `erstellt` → `gepostet` |
| `countdown` *(optional)* | eigene Zeit in Sekunden für genau dieses Rätsel, z. B. `6` |
| `tipp` *(optional)* | erscheint in der zweiten Hälfte des Countdowns als „💡 Tipp: …“ mit hellem Pling – nur für sehr harte Rätsel verwenden |
| `thema` *(optional)* | z. B. `halloween`, `weihnachten`, `gaming` – siehe „Themen & Trends“ |
| `optionen` *(optional, derzeit nicht genutzt)* | 2–4 Antwortvorgaben A/B/C. Bewusst abgeschaltet, weil Vorgaben zum Raten verleiten – die Funktion bleibt für spätere Tests erhalten |
| `hook` *(optional)* | eigener Spruch oben statt dem zufälligen aus `config.json` |
| `bild` *(optional)* | Pfad zu einem Bild, z. B. `"assets/bilder/100.png"` – wird über dem Text angezeigt (für Bildrätsel) |

**Tipps für den Rätseltext:**

- `*Sternchen*` um Wörter setzen → erscheinen in der Akzentfarbe: `"Wie viele *Dreiecke* siehst du?"`
- `\n` erzwingt einen Zeilenumbruch: `"Welche Zahl kommt als Nächstes?\n2 – 6 – 12 – ?"`
- Damit eine Zahlenreihe nicht mitten drin umbricht, statt normaler Leerzeichen geschützte Leerzeichen verwenden (` `), wie in Rätsel 12.
- Emojis funktionieren überall (Rätsel, Sprüche, Optionen). Am besten einfache Emojis ohne Hautfarben oder Kombinationen.
- Kürzere Texte werden größer dargestellt. Ideal sind 1–3 kurze Sätze.

**Was ein gutes Rätsel ausmacht:** eine eindeutige Lösung, die man durch Nachdenken herausfinden kann (kein Wissen, kein Schätzen), möglichst mit einer Falle, in die man schnell tappt.

Danach `python generate.py --vorschau` ausführen und die PNGs in `output/` anschauen.

### Themen & Trends

Ein Rätsel kann ein `thema` bekommen, z. B. `"thema": "halloween"`. Dann trägt es die Plakette, Farbe, Sprüche und Hashtags des Themas (in `config.json` unter `themen`). Vorhanden: `halloween`, `herbst`, `weihnachten`, `silvester`, `gaming`.

- **Zeitraum:** Themen können einen `zeitraum` haben (z. B. `["10-01", "10-31"]`). Der Posting-Plan setzt solche Rätsel nur in diesem Zeitraum ein – und bevorzugt sie, damit sie nicht ablaufen. Was nicht mehr passt, bleibt bis zum nächsten Jahr liegen.
- **Neues Thema:** einfach einen Block unter `themen` ergänzen (`label`, optional `akzent`, `zeitraum`, `hashtags`, `captions`, `texte.hook`).
- **Faustregeln für Trend-Rätsel:** Das Thema ist nur die Verpackung, die Lösung muss sich logisch herleiten lassen. Keine echten Preise, Termine oder Zahlen aus den News ins Rätsel (die ändern sich und lösen Diskussionen über Fakten statt über die Lösung aus) – lieber „Eine Konsole kostet 500 € …“. Politik und echte Promis meiden.

### Archiv

`raetsel_archiv.json` enthält zurückgestellte Rätsel – die Wissensfragen und die sehr schweren bzw. sehr textlastigen Rätsel. Zum Wiederverwenden einen Eintrag einfach zurück in `raetsel.json` kopieren.

### Neue Kategorie anlegen

In `config.json` unter `kategorien` einen Block ergänzen:

```json
"geschichte": {
  "label": "GESCHICHTE",
  "akzent": "#EB5757",
  "hashtags": ["#geschichte", "#quiz", "#wissen", "#allgemeinwissen", "#history"],
  "captions": ["Weißt du's? 🤔", "Geschichts-Check! 🧠"],
  "texte": { "hook": ["Nur echte Geschichtsprofis wissen das 📜"] }
}
```

- `label` – Text der kleinen Plakette oben im Video
- `akzent` *(optional)* – eigene Akzentfarbe für diese Kategorie; ohne Angabe gilt das IQKnacker-Gelb
- `hashtags` – Pool, aus dem pro Video passend ausgewählt wird (zusätzlich zu `hashtags_allgemein`)
- `captions` – Caption-Sätze, pro Rätsel wird einer ausgewählt (immer derselbe für dieselbe ID). `{countdown}` wird durch die Countdown-Länge ersetzt.
- `texte` *(optional)* – überschreibt einzelne Sprüche nur für diese Kategorie (gleiche Schlüssel wie unter `texte`, siehe unten)
- `caption_aufruf` *(optional)* – eigene Aufforderung in der Caption, z. B. „Schreib Reihe & Spalte in die Kommentare 👇“
- `zeilenabstand`, `raetsel_max` *(optional)* – eigener Zeilenabstand bzw. maximale Schriftgröße (die Emoji-Gleichungen nutzen das)

---

## Sprüche ändern

Alle Sprüche stehen in `config.json` unter `texte`. Jeder Eintrag darf ein einzelner Text, eine **Liste** (pro Rätsel wird zufällig einer gewählt – immer derselbe für dieselbe ID) oder eine Liste **je Schwierigkeit** sein:

| Schlüssel | Wann er erscheint |
|---|---|
| `hook` | ab dem ersten Frame über dem Rätsel – je `leicht` / `mittel` / `schwer`, `standard` als Ersatz |
| `spruch_mitte` | 6 Sekunden vor Schluss bzw. frühestens 2,5 s nach Start (nur ohne `tipp`, bei sehr kurzen Countdowns entfällt er) |
| `spruch_kritisch` | in der Schlussphase (letzte 2–3 Sekunden), in Rot (nur ohne `tipp`) |
| `tipp_prefix` | Text vor jedem Tipp, Standard „💡 *Tipp:* “ |
| `zeit_um` | große Einblendung, wenn die Zeit abgelaufen ist |
| `pause_1` – `pause_3` | Kommentar-Pause vor der Auflösung („*Jetzt* kommentieren!“ …) |
| `aufloesung_label` | Text der grünen Plakette („AUFLÖSUNG“) |
| `abschluss_1` – `abschluss_3` | Abschluss nach der Auflösung („Hattest du's?“ …) |
| `endkarte_1`, `endkarte_2` | Endkarte – nur bei Videos ohne Auflösung (`--ohne-aufloesung`) |

Platzhalter: `{countdown}` → Countdown-Sekunden, `{buchstaben}` → „A, B oder C“. `*Sternchen*` heben Wörter farbig hervor.

---

## Design ändern

Alles steht zentral in **`config.json`**:

| Bereich | Was du dort einstellst |
|---|---|
| `farben` | Hintergrund, Text, Akzent (`#F2C94C`), Warnfarbe für die Schlussphase (`warnung`), Label-Schrift, Ring-Hintergrund, Antwort-Kästen (`option_hintergrund`, `option_rand`) |
| `schriften` | Pfade zu den Schriftdateien (`.ttf`) |
| `groessen` | Schriftgrößen für Spruch (`banner`), Label, Rätsel (max/min), Antwort-Kästen, Suchrätsel-Frage, Countdown-Zahl und -Ring (`countdown_ring_klein` mit Antworten oder Gitter), „Zeit um“, Endkarte |
| `zeiten` | **Lesezeit** (`zeichen_pro_sekunde`, `min`, `max` – oder eine feste Zahl), **Denkzeit je Schwierigkeit** (`countdown`: leicht 5, mittel 7, schwer 10 s), „Zeit um“, Abschluss, Endkarte, Übergänge, `loop` (Überblendung zum Anfang, `0` = aus). Einzelne Rätsel können `lesezeit` und `countdown` selbst festlegen. |
| `aufloesung` | `zeigen` (Lösung im Video an/aus), Länge der Kommentar-Pause, Lesetempo und Mindest-/Höchstdauer der Auflösung |
| `animation` | Start-Zoom, langsamer Zoom, Spruch-Wechsel, wann Tipp und Sprüche kommen, Puls der Countdown-Zahl, ab wann es rot wird (`kritisch_ab`), Leuchten (`glow_deckkraft`), roter Rand (`vignette_deckkraft`), Anzahl der Lichtpunkte im Hintergrund (`partikel`, `0` = aus) |
| `countdown.stil` | `"ring"` (Kreis mit Zahl), `"zahlen"`, `"balken"` oder `"beides"` (Zahl + Balken) |
| `wasserzeichen` | Logo-Datei, Position (`oben_links`, `oben_rechts`, `unten_links`, `unten_rechts`), Höhe, Deckkraft |
| `safe_zone` | freie Ränder für die TikTok-Oberfläche (oben 150, unten 400, rechts 150 px) |
| `musik` | `modus`, Ordner, Lautstärke, Ein-/Ausblenden (siehe unten) |
| `soundeffekte` | Ticken, Tipp-Pling und Gong an/aus (`aktiv`), Lautstärke |
| `audio.lautheit_lufs` | Gesamtlautheit des Tons (Standard −14 LUFS, üblich für Social Media) |
| `hashtags_allgemein`, `hashtags_anzahl` | immer verwendete Hashtags, Anzahl insgesamt (5–8) |
| `caption_aufruf_aufloesung`, `caption_aufruf` | Aufforderung in der Caption – mit bzw. ohne Auflösung im Video |
| `kommentar_vorlage_aufloesung`, `kommentar_vorlage` | Text der Kommentar-Datei – mit bzw. ohne Auflösung im Video (`{loesung}`, `{erklaerung}`, …) |

**Andere Schrift:** `.ttf` von [Google Fonts](https://fonts.google.com) herunterladen (z. B. *Anton*), in `assets/fonts/` legen und in `config.json` unter `schriften.fett` eintragen.

**Tipp:** Nach jeder Design-Änderung `python generate.py --id 15 --vorschau` – das dauert nur eine Sekunde.

---

## Musik, Soundeffekte & Logo

- **Musik (`musik.modus`):**
  - `"auto"` *(Standard)*: Liegen MP3s (auch M4A/WAV/OGG) in `assets/music/`, wird pro Video zufällig einer gewählt, auf Videolänge geschnitten und ausgeblendet. **Ohne Dateien erzeugt das Skript die Musik selbst** – ruhig während der Lesezeit, ab dem Countdown mit Beat im Takt der Ticks, in der Schlussphase doppelt so schnell, Einschlag bei „Zeit um!“, Herzschlag bei „3 · 2 · 1“, ein heller Dur-Klang zur Auflösung und ein ruhiger Ausklang bis zum Loop. Jedes Rätsel bekommt eine eigene Tonart und Akkordfolge. Keine Lizenzfragen.
  - `"generiert"`: immer die selbst erzeugte Musik, auch wenn Dateien da sind
  - `"dateien"`: nur deine Tracks (ohne Dateien keine Musik)
  - `"aus"`: keine Musik
- **Soundeffekte:** Ticken pro Countdown-Sekunde (in der Schlussphase höher und doppelt), ein helles Pling beim Tipp, ein Gong bei „Zeit um!“, leises Ticken bei „3 · 2 · 1“ und ein heller Klang, wenn die Lösung erscheint – alles vom Skript erzeugt.
- **Trend-Sound in der App:** Videos mit `--ohne-musik` erzeugen (Ticken bleibt) oder mit `--ohne-musik --ohne-effekte` ganz ohne Ton.
- **Logo:** `assets/logo/logo_symbol.png` (nur Symbol) und `assets/logo/logo_komplett.png` (mit Schriftzug), PNG mit transparentem Hintergrund. Wird klein als Wasserzeichen oben links eingeblendet. Solange keine Datei da ist, steht dort `@iqknacker` als Text. `assets/logo/profilbild.png` ist das Profilbild für den Account.

---

## Ordnerstruktur

```
IQKnacker/
├── generate.py        # Kommandozeile, Daten, Captions, Ton, FFmpeg
├── renderer.py        # Frames & Animationen (Pillow)
├── musik.py           # erzeugt die Hintergrundmusik passend zum Countdown
├── automatik.py       # baut Emoji-Gleichungen und Suchrätsel samt Lösung
├── config.json        # Design, Zeiten, Sprüche, Kategorien
├── raetsel.json       # deine Rätsel
├── raetsel_archiv.json # zurückgestellte Rätsel (Wissensfragen, sehr schwere)
├── requirements.txt
├── assets/
│   ├── fonts/         # Montserrat ExtraBold/Bold + Noto Color Emoji
│   ├── logo/          # dein Logo + Profilbild
│   └── music/         # optional: eigene Tracks
└── output/            # fertige Videos, Vorschaubilder, Texte
```

Schriften: Montserrat und Noto Color Emoji stehen unter der SIL Open Font License 1.1 (siehe `assets/fonts/LIZENZ.txt`).
