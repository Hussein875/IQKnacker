# Ideen-Topf

Ideen für später – erst angehen, wenn die ersten Zahlen aus TikTok Studio da sind.

## Neue Rätselarten
- **„Finde den Fehler“** als eigene Kategorie: Der Fehler ist absichtlich drin und *ist* die Aufgabe
  (z. B. doppeltes Wort „Paris im im Frühling“, falscher Rechenschritt, „1 – 2 – 3 … – wo ist der Fehler?“).
  Die Auflösung bleibt immer korrekt.
- Mehr Rätsel der Art, die laut Statistik am besten läuft.

## Community
- **Wochen-Bestenliste** als Video („Die schnellsten Rätsel-Knacker der Woche 🏆“), sobald regelmäßig Kommentare kommen.
- **Feste Serien**, z. B. jeden Sonntag ein „Genie-Rätsel“.
- Mit Video auf besonders gute oder lustige Kommentare antworten.

## Themen & Trends
- Weitere Themen mit Zeitraum anlegen: Valentinstag, Ostern, Sommer/Ferien, Schulstart, große Spiele-Releases, Fußball-Turniere.
- Faustregel: Thema = Verpackung, Lösung = Logik. Keine echten Preise/Termine aus den News, keine Politik, keine echten Promis.

## Reichweite
- Dieselben Videos auch als Instagram Reels und YouTube Shorts posten.
- Eigene Musik-Tracks oder Trend-Sounds gegen die erzeugte Musik testen.
- Vergleich mit/ohne Auflösung im Video (`--ohne-aufloesung`), falls die Zahlen dafür sprechen.

## Internationalisierung (später)
- Wenn es auf Deutsch läuft: dieselben Rätsel auf **Englisch** (größter Markt) und ggf. weiteren Sprachen anbieten.
- Am besten als **eigener Account pro Sprache**, damit der Algorithmus die Zielgruppe sauber zuordnen kann.
- Technisch: Texte und Sprüche aus `config.json` und `raetsel.json` pro Sprache übersetzen (z. B. `config_en.json`, `raetsel_en.json`).
  Zahlen-, Emoji- und Suchrätsel lassen sich fast 1:1 übernehmen; Wort- und Buchstabenrätsel brauchen eigene Versionen
  (z. B. „J – F – M – A – M“ funktioniert auf Englisch, „E – Z – D – V“ nicht).

## Zweiter Kanal: „Falsche Wahl“ (@falschewahl, Alltags-Vergleiche) – Konzept steht, Start nach der IQKnacker-Testphase

- **Ziel:** viral gehen. Themen: vor allem Geld & Alltag, aber auch Zeit, Essen, Technik, Strom usw. Junge, breite Zielgruppe (ca. 16–35), frecher Ton, aber immer echte, nachgerechnete Zahlen.
- **Format:** Faktenvideos, kein Quiz. Hauptformat **A vs. B** (wie das Kaffee-Muster): zwei Karten, Preis pro Stück,
  Balken „pro Jahr“, große Differenz mit „In 10 Jahren …“, Kommentar- und Teil-Frage. Abwechselnd mit
  „Rechnung + Pointe“ (Döner-Muster), „Was steckt drin?“, „Damals vs. heute“, „In Perspektive“.
- **Ideen:** Auto vs. Deutschlandticket · Mieten vs. Kaufen · Kaffee to go vs. Zuhause · Abo-Fallen · Brutto vs. Netto ·
  Neu- vs. Gebrauchtwagen · Lieferdienst vs. selbst kochen · Handyvertrag vs. Prepaid · Döner, Kino, Miete: 2000 vs. heute.
- **Regeln:** keine Anlageberatung; echte Zahlen nur mit Quelle + Stand, sonst als *Beispielrechnung* kennzeichnen.
- **Stimme:** ja – mit ElevenLabs (Starter ca. 5–6 $/Monat, ~30.000 Zeichen ≈ 90 Videos; Preise vorher prüfen).
  Immer zusätzlich Text im Bild (Instagram läuft oft stumm). Bei KI-Stimme „KI-generiert“ aktivieren.
- **Technik:** eigenes Repository, eigener Drive-Ordner, zweite Marke in Metricool (Starter erlaubt 5),
  eigene Cloud-Aufgaben. Prototyp: `prototypen/lohntsich.py` (Muster Kaffee + Döner, mit Test-Stimme; Marke dort noch „LOHNTSICH?“).
- **Name:** „Falsche Wahl“, Handle `@falschewahl` (auf TikTok frei). Frech-provokant und bewusst nicht nur Geld:
  Vergleiche aus dem ganzen Alltag (Geld, Zeit, Essen, Technik, Strom …), jedes Video zeigt, welche Wahl die falsche ist.
  Reserve-Handles (frei): `@imvergleich`, `@vergleichsmal`, `@kurzverglichen`. Verworfen u. a.: @lohntsich/@lohntsichdas
  (vergeben bzw. BR-Format), @zahlenduell, @besserwissen, @utrum, @pondero (vergeben).
- **To-do vor dem Start:** Handle auf allen drei Plattformen sichern, ElevenLabs-Konto + deutsche Stimme
  aussuchen, API-Schlüssel lokal auf dem Mac hinterlegen (nie in den Chat oder ins Repo).
