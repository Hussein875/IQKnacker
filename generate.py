#!/usr/bin/env python3
"""IQKnacker Video-Generator.

Beispiele:
    python generate.py                 # alle Rätsel mit Status "neu"
    python generate.py --id 5          # nur Rätsel 5 (egal welcher Status)
    python generate.py --id 3 7 9      # mehrere Rätsel
    python generate.py --alle          # alle Rätsel neu erzeugen
    python generate.py --vorschau      # nur Vorschaubilder (PNG), kein Video
    python generate.py --liste         # Rätsel mit Status anzeigen
    python generate.py --check         # Installation prüfen
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time

BASIS = os.path.dirname(os.path.abspath(__file__))
CONFIG_DATEI = os.path.join(BASIS, "config.json")
RAETSEL_DATEI = os.path.join(BASIS, "raetsel.json")
PFLICHTFELDER = ["id", "kategorie", "frage", "loesung", "erklaerung", "schwierigkeit", "status"]
GUELTIGE_STATUS = ["neu", "erstellt", "gepostet"]
MUSIK_ENDUNGEN = (".mp3", ".m4a", ".aac", ".wav", ".ogg")
KOMMENTAR_MAX = 150  # Zeichenlimit für TikTok-Kommentare


# ---------------------------------------------------------------- Umgebung prüfen

def pip_installieren():
    print("→ Installiere fehlende Python-Pakete aus requirements.txt ...")
    befehl = [sys.executable, "-m", "pip", "install", "-r", os.path.join(BASIS, "requirements.txt")]
    if subprocess.call(befehl) != 0:
        sys.exit("✗ Installation fehlgeschlagen. Bitte manuell ausführen:\n  " + " ".join(befehl))


def pillow_sicherstellen():
    try:
        import PIL  # noqa: F401
    except ImportError:
        pip_installieren()


def ffmpeg_finden(installieren=True):
    pfad = shutil.which("ffmpeg")
    if pfad:
        return pfad
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    if installieren:
        pip_installieren()
        return ffmpeg_finden(installieren=False)
    sys.exit("✗ FFmpeg nicht gefunden. Installiere es z. B. mit\n"
             "  macOS:   brew install ffmpeg\n"
             "  Windows: winget install ffmpeg\n"
             "  Linux:   sudo apt install ffmpeg")


def check():
    print(f"Python:  {sys.version.split()[0]}", "✓" if sys.version_info >= (3, 8) else "✗ (mind. 3.8 nötig)")
    pillow_sicherstellen()
    import PIL
    print(f"Pillow:  {PIL.__version__} ✓")
    ffmpeg = ffmpeg_finden()
    version = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True).stdout.split("\n")[0]
    print(f"FFmpeg:  {version} ✓\n         ({ffmpeg})")
    cfg = lade_json(CONFIG_DATEI)
    for name, pfad in cfg["schriften"].items():
        voll = os.path.join(BASIS, pfad)
        print(f"Schrift {name}: {pfad}", "✓" if os.path.exists(voll) else "✗ fehlt")
    musik = musik_dateien(cfg)
    print(f"Musik:   {len(musik)} Track(s) in {cfg['musik']['ordner']}" + ("" if musik else " (Videos werden stumm)"))
    logo = os.path.join(BASIS, cfg["wasserzeichen"]["datei"])
    print(f"Logo:    {'✓ ' + cfg['wasserzeichen']['datei'] if os.path.exists(logo) else '– nicht gefunden, nutze Text-Wasserzeichen'}")


# ---------------------------------------------------------------- Daten

def lade_json(pfad):
    with open(pfad, encoding="utf-8") as f:
        return json.load(f)


def speichere_raetsel(raetsel):
    tmp = RAETSEL_DATEI + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(raetsel, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, RAETSEL_DATEI)


def pruefe_raetsel(raetsel, cfg):
    fehler, ids = [], set()
    for i, r in enumerate(raetsel):
        fehlend = [f for f in PFLICHTFELDER if f not in r]
        if fehlend:
            fehler.append(f"Eintrag {i + 1}: Felder fehlen: {', '.join(fehlend)}")
            continue
        if r["id"] in ids:
            fehler.append(f"Rätsel-ID {r['id']} kommt doppelt vor")
        ids.add(r["id"])
        if r["status"] not in GUELTIGE_STATUS:
            fehler.append(f"Rätsel {r['id']}: unbekannter Status „{r['status']}“ (erlaubt: {', '.join(GUELTIGE_STATUS)})")
        if r["kategorie"] not in cfg["kategorien"]:
            print(f"⚠ Rätsel {r['id']}: Kategorie „{r['kategorie']}“ ist nicht in config.json – nutze Standard-Design.")
    if fehler:
        sys.exit("✗ Fehler in raetsel.json:\n  " + "\n  ".join(fehler))


def dateiname(r):
    return f"{int(r['id']):03d}_{r['kategorie']}"


# ---------------------------------------------------------------- Texte (Caption, Kommentar)

def caption_text(r, cfg):
    kat = cfg["kategorien"].get(r["kategorie"], {})
    zufall = random.Random(f"{r['id']}-{r['kategorie']}")  # gleiche ID → gleiche Caption
    captions = kat.get("captions") or ["Kannst du das lösen? 🧠"]
    caption = zufall.choice(captions)

    allgemein = list(cfg.get("hashtags_allgemein", []))
    eigene = [h for h in kat.get("hashtags", []) if h not in allgemein]
    anzahl = max(5, min(8, cfg.get("hashtags_anzahl", 7)))
    zusatz = zufall.sample(eigene, min(len(eigene), max(0, anzahl - len(allgemein))))
    hashtags = (allgemein[:1] + zusatz + allgemein[1:])[:anzahl]

    return f"{caption}\nSchreib deine Antwort in die Kommentare 👇\n\n{' '.join(hashtags)}\n"


def kommentar_text(r, cfg):
    return cfg["kommentar_vorlage"].format(**r).strip() + "\n"


# ---------------------------------------------------------------- Musik & Rendering

def musik_dateien(cfg):
    ordner = os.path.join(BASIS, cfg["musik"]["ordner"])
    if not os.path.isdir(ordner):
        return []
    return sorted(os.path.join(ordner, f) for f in os.listdir(ordner)
                  if f.lower().endswith(MUSIK_ENDUNGEN) and not f.startswith("."))


def ffmpeg_befehl(ffmpeg, renderer, ziel, cfg, musik):
    v = cfg["video"]
    dauer = renderer.dauer
    befehl = [ffmpeg, "-y", "-loglevel", "error",
              "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{renderer.breite}x{renderer.hoehe}",
              "-r", str(renderer.fps), "-i", "-"]
    if musik:
        m = cfg["musik"]
        aus = min(m["ausblenden"], dauer)
        befehl += ["-stream_loop", "-1", "-i", musik]
        filter_audio = (f"[1:a]atrim=0:{dauer:.3f},asetpts=N/SR/TB,"
                        f"afade=t=in:st=0:d={m['einblenden']},"
                        f"afade=t=out:st={dauer - aus:.3f}:d={aus},"
                        f"volume={m['lautstaerke']}[a]")
        befehl += ["-filter_complex", filter_audio, "-map", "0:v", "-map", "[a]"]
    else:
        # Stille Tonspur, damit sich das Video überall problemlos weiterbearbeiten lässt
        befehl += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-map", "0:v", "-map", "1:a"]
    befehl += ["-t", f"{dauer:.3f}",
               "-c:v", "libx264", "-preset", v["preset"], "-crf", str(v["qualitaet_crf"]),
               "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(renderer.fps),
               "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
               "-movflags", "+faststart", ziel]
    return befehl


def erzeuge(r, cfg, ffmpeg, nur_vorschau=False, ohne_musik=False):
    from renderer import RaetselRenderer

    ausgabe = os.path.join(BASIS, cfg["ausgabe"]["ordner"])
    os.makedirs(ausgabe, exist_ok=True)
    name = dateiname(r)
    renderer = RaetselRenderer(cfg, r, BASIS)

    vorschau = os.path.join(ausgabe, f"{name}.png")
    renderer.frame(renderer.vorschau_zeitpunkt()).save(vorschau)

    if nur_vorschau:
        print(f"  ✓ Vorschau: {os.path.relpath(vorschau, BASIS)} (Schriftgröße {renderer.raetsel_schriftgroesse})")
        return

    musik_liste = [] if ohne_musik else musik_dateien(cfg)
    musik = random.choice(musik_liste) if musik_liste else None
    video = os.path.join(ausgabe, f"{name}.mp4")
    tmp = os.path.join(ausgabe, f".{name}.tmp.mp4")

    start = time.time()
    prozess = subprocess.Popen(ffmpeg_befehl(ffmpeg, renderer, tmp, cfg, musik), stdin=subprocess.PIPE)
    try:
        for i in range(renderer.frame_anzahl):
            prozess.stdin.write(renderer.frame(i / renderer.fps).tobytes())
        prozess.stdin.close()
    except BrokenPipeError:
        pass
    if prozess.wait() != 0:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise RuntimeError("FFmpeg ist mit einem Fehler abgebrochen (siehe Meldung oben).")
    os.replace(tmp, video)

    with open(os.path.join(ausgabe, f"{name}_caption.txt"), "w", encoding="utf-8") as f:
        f.write(caption_text(r, cfg))
    kommentar = kommentar_text(r, cfg)
    with open(os.path.join(ausgabe, f"{name}_kommentar.txt"), "w", encoding="utf-8") as f:
        f.write(kommentar)

    musik_info = os.path.basename(musik) if musik else "ohne Musik"
    print(f"  ✓ {os.path.relpath(video, BASIS)}  ({renderer.dauer:.1f} s, {musik_info}, "
          f"Schriftgröße {renderer.raetsel_schriftgroesse}, {time.time() - start:.1f} s Renderzeit)")
    if len(kommentar.strip()) > KOMMENTAR_MAX:
        print(f"  ⚠ Auflösungs-Kommentar hat {len(kommentar.strip())} Zeichen – TikTok erlaubt {KOMMENTAR_MAX}. "
              f"Erklärung kürzen!")


# ---------------------------------------------------------------- Kommandozeile

def main():
    parser = argparse.ArgumentParser(description="IQKnacker: erzeugt Rätsel-Videos aus raetsel.json")
    parser.add_argument("--id", type=int, nargs="+", help="nur diese Rätsel-ID(s) erzeugen (egal welcher Status)")
    parser.add_argument("--alle", action="store_true", help="alle Rätsel erzeugen, egal welcher Status")
    parser.add_argument("--vorschau", action="store_true", help="nur Vorschaubilder, kein Video, Status bleibt")
    parser.add_argument("--ohne-musik", action="store_true", help="Video ohne Musik erzeugen")
    parser.add_argument("--liste", action="store_true", help="alle Rätsel mit Status anzeigen")
    parser.add_argument("--check", action="store_true", help="Installation prüfen")
    args = parser.parse_args()

    if args.check:
        check()
        return

    cfg = lade_json(CONFIG_DATEI)
    raetsel = lade_json(RAETSEL_DATEI)
    pruefe_raetsel(raetsel, cfg)

    if args.liste:
        for r in raetsel:
            frage = r["frage"].replace("\n", " ").replace("*", "")
            print(f"{r['id']:>4}  {r['status']:<9} {r['kategorie']:<7} {frage[:60]}")
        return

    if args.id:
        auswahl = [r for r in raetsel if r["id"] in args.id]
        fehlend = set(args.id) - {r["id"] for r in auswahl}
        if fehlend:
            sys.exit(f"✗ Rätsel-ID(s) nicht gefunden: {', '.join(map(str, sorted(fehlend)))}")
    elif args.alle:
        auswahl = raetsel
    else:
        auswahl = [r for r in raetsel if r["status"] == "neu"]

    if not auswahl:
        print("Keine neuen Rätsel. Neue Einträge mit \"status\": \"neu\" in raetsel.json anlegen "
              "oder --id / --alle nutzen.")
        return

    pillow_sicherstellen()
    ffmpeg = None if args.vorschau else ffmpeg_finden()

    print(f"Erzeuge {len(auswahl)} {'Vorschau(en)' if args.vorschau else 'Video(s)'} ...")
    fehler = 0
    for r in auswahl:
        print(f"• Rätsel {r['id']} ({r['kategorie']})")
        try:
            erzeuge(r, cfg, ffmpeg, nur_vorschau=args.vorschau, ohne_musik=args.ohne_musik)
        except Exception as e:
            fehler += 1
            print(f"  ✗ Fehler: {e}")
            continue
        if not args.vorschau and r["status"] == "neu":
            r["status"] = "erstellt"
            speichere_raetsel(raetsel)  # nach jedem Video speichern, damit nichts verloren geht

    print("Fertig." if not fehler else f"Fertig mit {fehler} Fehler(n).")
    if fehler:
        sys.exit(1)


if __name__ == "__main__":
    main()
