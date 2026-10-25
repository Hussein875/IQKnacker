"""Erzeugt spannende Hintergrundmusik, die im Takt zum Countdown pulsiert.

Alles ist synthetisch – keine Musikdateien, keine Lizenzfragen. Jedes Rätsel bekommt
eine eigene Variante (Tonart und Akkordfolge), die beim erneuten Rendern gleich bleibt.

Aufbau: dumpfer Schlag zum Einstieg → ruhige Lesephase ohne Beat → pulsierender Beat mit 120 BPM
ab dem Countdown (jeder zweite Schlag fällt genau auf einen Tick) → Schlussphase doppelt so schnell
mit Anstieg → Einschlag bei „Zeit um!“ → Herzschlag bei „3 · 2 · 1“ → heller Dur-Klang zur
Auflösung → ruhiger Ausklang, der nahtlos in den Loop übergeht.
"""

import random
import wave

import numpy as np

RATE = 44100
SCHLAG = 0.5        # Sekunden pro Schlag (120 BPM)
TAKT = 4 * SCHLAG   # ein Akkord pro Takt

# Akkordstufen relativ zum Grundton einer Moll-Tonart: (Halbtöne, Tongeschlecht)
AKKORDFOLGEN = [
    [(0, "moll"), (-4, "dur"), (3, "dur"), (-2, "dur")],   # i – VI – III – VII
    [(0, "moll"), (-4, "dur"), (5, "moll"), (-5, "dur")],  # i – VI – iv – V
    [(0, "moll"), (0, "moll"), (-4, "dur"), (-5, "dur")],  # i – i – VI – V
    [(0, "moll"), (-2, "dur"), (-4, "dur"), (-5, "dur")],  # i – VII – VI – V
]
SPANNUNGSAKKORD = (-5, "dur")          # Dominante: will sich auflösen → maximale Spannung
GRUNDTOENE = [55, 57, 59, 60, 62]      # G, A, H, C, D (MIDI-Nummern, Moll)


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def akkord(grundton, stufe):
    versatz, art = stufe
    terz = 3 if art == "moll" else 4
    return [grundton + versatz, grundton + versatz + terz, grundton + versatz + 7]


def zeitachse(dauer):
    return np.arange(max(1, int(round(dauer * RATE)))) / RATE


class Spur:
    """Stereo-Spur, in die Klänge an beliebigen Zeitpunkten eingemischt werden."""

    def __init__(self, dauer):
        self.n = int(round(dauer * RATE))
        self.daten = np.zeros((self.n, 2))

    def mische(self, start, signal, lautstaerke=1.0, pan=0.0):
        i0 = int(round(start * RATE))
        if i0 < 0:
            signal, i0 = signal[-i0:], 0
        signal = signal[: max(0, self.n - i0)]
        if len(signal) == 0:
            return
        bereich = slice(i0, i0 + len(signal))
        self.daten[bereich, 0] += signal * lautstaerke * np.sqrt((1 - pan) / 2)
        self.daten[bereich, 1] += signal * lautstaerke * np.sqrt((1 + pan) / 2)


# ---------------------------------------------------------------- Instrumente

def flaeche(frequenzen, dauer, attack=0.1, release=0.3, verstimmung=0.08):
    """Weicher Synthesizer-Teppich: pro Ton zwei leicht verstimmte, gedämpfte Sägezahn-Stimmen."""
    t = zeitachse(dauer + release)
    signal = np.zeros_like(t)
    for f in frequenzen:
        for d in (-verstimmung, verstimmung):
            phase = 2 * np.pi * f * 2 ** (d / 12) * t
            for k in range(1, 6):
                signal += np.sin(k * phase) / k ** 1.5
    huelle = np.minimum(1, t / max(attack, 1e-3)) * np.clip((dauer + release - t) / release, 0, 1)
    return signal * huelle / (2 * len(frequenzen))


def bass(f, dauer):
    t = zeitachse(dauer)
    signal = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t)
    huelle = np.minimum(1, t / 0.004) * np.exp(-t * 7) * np.clip((dauer - t) / 0.01, 0, 1)
    return np.tanh(1.5 * signal * huelle) / np.tanh(1.5)


def kick(dauer=0.4):
    t = zeitachse(dauer)
    phase = 2 * np.pi * (45 * t + 75 / 30 * (1 - np.exp(-30 * t)))
    return np.sin(phase) * np.exp(-t * 9) * np.minimum(1, t / 0.002)


def hihat(rng, dauer=0.04):
    t = zeitachse(dauer)
    rauschen = np.diff(rng.standard_normal(len(t)), prepend=0.0)
    return rauschen * np.exp(-t * 110) * 0.5


def zupfen(f, dauer=0.25):
    """Kurzer, heller Ton (Dreieckswelle) für Arpeggios."""
    t = zeitachse(dauer)
    signal = 2 / np.pi * np.arcsin(np.sin(2 * np.pi * f * t))
    return signal * np.minimum(1, t / 0.003) * np.exp(-t * 14)


def anstieg(rng, dauer, f_start, f_ende):
    """Rauschen und Ton, die bis zum Ende immer lauter und höher werden."""
    t = zeitachse(dauer)
    rauschen = np.diff(rng.standard_normal(len(t)), prepend=0.0) * 0.4
    f = f_start * (f_ende / f_start) ** (t / dauer)
    ton = np.sin(2 * np.pi * np.cumsum(f) / RATE)
    return (0.6 * rauschen + 0.4 * ton) * (t / dauer) ** 2


def einschlag(rng, dauer=1.8):
    """Tiefer, dumpfer Schlag (Kino-„Boom“)."""
    t = zeitachse(dauer)
    sub = np.sin(2 * np.pi * (32 * t + 45 / 5 * (1 - np.exp(-5 * t)))) * np.exp(-t * 2.0)
    rauschen = np.convolve(rng.standard_normal(len(t)), np.ones(24) / 24, mode="same")
    knall = rauschen * np.exp(-t * 9) * 3
    return (sub + knall) * np.minimum(1, t / 0.002)


# ---------------------------------------------------------------- Komposition

def erzeuge_musik(renderer, ziel, saat):
    """Schreibt eine Stereo-WAV in Videolänge, abgestimmt auf den Countdown des Renderers."""
    zufall = random.Random(saat)
    rng = np.random.default_rng(zufall.randrange(2 ** 32))
    grund = zufall.choice(GRUNDTOENE)
    folge = zufall.choice(AKKORDFOLGEN)

    dauer = renderer.dauer
    start = renderer.countdown_start()
    ende = renderer.zeit_um_zeitpunkt()
    kritisch_ab = ende - min(renderer.kritisch_ab, renderer.t_countdown)

    flaechen = Spur(dauer)  # bekommt das „Pumpen“ im Takt
    rest = Spur(dauer)

    # Lesephase: Schlag auf den ersten Frame, dann ruhige Fläche mit leisem Arpeggio – noch ohne Beat.
    # Die Takte liegen rückwärts vom Countdown-Start aus, damit alles im selben Raster bleibt; der
    # letzte Takt vor dem Countdown ist der vierte Akkord der Folge, der Countdown beginnt mit dem ersten.
    rest.mische(0, einschlag(rng, 1.2), 0.3)
    takte, t = [], start
    while t > 1e-6:
        takte.append((max(0.0, t - TAKT), t))
        t -= TAKT
    for k, (a_start, a_ende) in enumerate(reversed(takte)):
        toene = akkord(grund, folge[(k - len(takte)) % len(folge)])
        flaechen.mische(a_start, flaeche([hz(n) for n in toene], a_ende - a_start, attack=0.6 if k == 0 else 0.1),
                        0.45)
        muster = [toene[0] + 12, toene[1] + 12, toene[2] + 12, toene[1] + 12]
        noten, t0 = [], a_ende - SCHLAG / 2
        while t0 >= a_start - 1e-6:
            noten.append(t0)
            t0 -= SCHLAG / 2
        for j, t0 in enumerate(reversed(noten)):
            rest.mische(t0, zupfen(hz(muster[j % 4])), 0.035, pan=0.3 if j % 2 else -0.3)

    # Countdown in Takten, die Schlussphase liegt auf dem Spannungsakkord
    abschnitte, t, i = [], start, 0
    while t < kritisch_ab - 1e-6:
        abschnitte.append((t, min(t + TAKT, kritisch_ab), folge[i % len(folge)], False))
        t, i = min(t + TAKT, kritisch_ab), i + 1
    if kritisch_ab < ende - 1e-6:  # beim ruhigen Countdown gibt es keine Schlussphase
        abschnitte.append((kritisch_ab, ende, SPANNUNGSAKKORD, True))

    for a_start, a_ende, stufe, kritisch in abschnitte:
        toene = akkord(grund, stufe)
        fortschritt = (a_start - start) / max(0.01, ende - start)
        flaechen.mische(a_start, flaeche([hz(n) for n in toene], a_ende - a_start), 0.55 + 0.3 * fortschritt)

        # Bass in Achteln, in der Schlussphase in Sechzehnteln
        raster = SCHLAG / (4 if kritisch else 2)
        k = 0
        while a_start + k * raster < a_ende - 1e-6:
            rest.mische(a_start + k * raster, bass(hz(toene[0] - 12), raster * 0.9), 0.30 if kritisch else 0.24)
            k += 1

        # Arpeggio ab dem zweiten Takt, in der Schlussphase doppelt so schnell und eine Oktave höher
        if kritisch or a_start >= start + TAKT - 1e-6:
            muster = [toene[0] + 12, toene[1] + 12, toene[2] + 12, toene[1] + 12]
            raster = SCHLAG / (4 if kritisch else 2)
            k = 0
            while a_start + k * raster < a_ende - 1e-6:
                ton = muster[k % 4] + (12 if kritisch and k % 8 >= 4 else 0)
                rest.mische(a_start + k * raster, zupfen(hz(ton)), 0.10 if kritisch else 0.06,
                            pan=0.35 if k % 2 else -0.35)
                k += 1

    # Schlagzeug: Kick auf jedem Tick (jede Sekunde), in der Schlussphase auf jedem Schlag
    k = 0
    while start + k * SCHLAG < ende - 1e-6:
        t0 = start + k * SCHLAG
        kritisch = t0 >= kritisch_ab - 1e-6
        if kritisch or k % 2 == 0:
            rest.mische(t0, kick(), 0.55 if kritisch else 0.45)
        teilung = 4 if kritisch else 2
        for u in range(1 if not kritisch else 0, teilung):
            rest.mische(t0 + u * SCHLAG / teilung, hihat(rng), 0.06 if kritisch else 0.045, pan=0.2)
        k += 1

    if kritisch_ab < ende - 1e-6:
        rest.mische(kritisch_ab, anstieg(rng, ende - kritisch_ab, hz(grund), hz(grund + 12)), 0.12)

    # „Zeit um!“: Einschlag
    rest.mische(ende, einschlag(rng), 0.7)
    aufloesung = renderer.aufloesung_zeitpunkt()
    if aufloesung is None:  # ohne Auflösung im Video: ruhiger Ausklang bis zum Loop
        ausklang = max(0.1, dauer - ende - 0.75)
        flaechen.mische(ende + 0.15, flaeche([hz(n) for n in akkord(grund, folge[0])], ausklang,
                                             attack=0.3, release=0.6), 0.45)
    else:
        # Spannung bis zur Auflösung: leise Dominante, Herzschlag auf „3 · 2 · 1“, kurzer Anstieg
        flaechen.mische(ende + 0.15, flaeche([hz(n) for n in akkord(grund, SPANNUNGSAKKORD)],
                                             max(0.1, aufloesung - ende - 0.15), attack=0.2, release=0.15), 0.35)
        for t0 in renderer.pause_ticks():
            rest.mische(t0, kick(), 0.32)
        if aufloesung - ende > 1.0:
            rest.mische(aufloesung - 0.8, anstieg(rng, 0.8, hz(grund), hz(grund + 12)), 0.08)
        # Auflösung: heller Dur-Akkord mit aufsteigendem Glitzern – klingt nach „gelöst!“
        dur = [grund, grund + 4, grund + 7]
        for k, n in enumerate([dur[0] + 12, dur[1] + 12, dur[2] + 12, dur[0] + 24]):
            rest.mische(aufloesung + k * 0.06, zupfen(hz(n), 0.6), 0.10)
        rest.mische(aufloesung, bass(hz(grund - 12), 0.6), 0.25)
        # ruhiger Ausklang in Dur (I – IV) mit leisem Arpeggio, endet kurz vor Schluss für den Loop
        t, k = aufloesung, 0
        while t < dauer - 0.8:
            toene = dur if k % 2 == 0 else [grund + 5, grund + 9, grund + 12]
            laenge = min(TAKT, dauer - 0.8 - t)
            flaechen.mische(t, flaeche([hz(n) for n in toene], laenge, attack=0.05 if k == 0 else 0.15,
                                       release=0.6), 0.42)
            for j in range(int(laenge / (SCHLAG / 2))):
                rest.mische(t + j * SCHLAG / 2, zupfen(hz([toene[0] + 12, toene[1] + 12, toene[2] + 12,
                                                          toene[1] + 12][j % 4])), 0.03, pan=0.3 if j % 2 else -0.3)
            t += TAKT
            k += 1

    # Pumpen im Takt (wie Sidechain-Kompression): Fläche wird nach jedem Schlag kurz leiser
    t = np.arange(flaechen.n) / RATE
    im_countdown = (t >= start) & (t < ende)
    pumpen = 1 - 0.4 * np.exp(-((t - start) % SCHLAG) * 9)
    flaechen.daten *= np.where(im_countdown, pumpen, 1.0)[:, None]

    mix = flaechen.daten + rest.daten
    blende = min(len(mix), int(0.05 * RATE))
    mix[-blende:] *= np.linspace(1, 0, blende)[:, None]  # sauberes Ende für den Loop
    spitze = np.max(np.abs(mix)) or 1.0
    mix = np.tanh(mix / spitze * 1.1) / np.tanh(1.1) * 0.89

    with wave.open(ziel, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    return {"grundton": grund, "folge": folge}
