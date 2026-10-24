"""Erzeugt spannende Hintergrundmusik, die im Takt zum Countdown pulsiert.

Alles ist synthetisch – keine Musikdateien, keine Lizenzfragen. Jedes Rätsel bekommt
eine eigene Variante (Tonart und Akkordfolge), die beim erneuten Rendern gleich bleibt.

Aufbau: dumpfer Schlag zum Einstieg → pulsierender Beat mit 120 BPM (jeder zweite Schlag
fällt genau auf einen Countdown-Tick) → Schlussphase doppelt so schnell mit Anstieg →
Einschlag bei „Zeit um!“ → ruhiger Ausklang, der nahtlos in den Loop übergeht.
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

    # Einstieg: Schlag auf den ersten Frame, Fläche schwillt bis zum Countdown an
    rest.mische(0, einschlag(rng, 1.2), 0.35)
    flaechen.mische(0, flaeche([hz(n) for n in akkord(grund, folge[0])], max(0.1, start),
                               attack=max(0.05, start * 0.8), release=0.3), 0.5)

    # Countdown in Takten, die Schlussphase liegt auf dem Spannungsakkord
    abschnitte, t, i = [], start, 0
    while t < kritisch_ab - 1e-6:
        abschnitte.append((t, min(t + TAKT, kritisch_ab), folge[i % len(folge)], False))
        t, i = min(t + TAKT, kritisch_ab), i + 1
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

    rest.mische(kritisch_ab, anstieg(rng, ende - kritisch_ab, hz(grund), hz(grund + 12)), 0.12)

    # „Zeit um!“: Einschlag, danach ruhiger Ausklang bis zum Loop
    rest.mische(ende, einschlag(rng), 0.7)
    ausklang = max(0.1, dauer - ende - 0.75)
    flaechen.mische(ende + 0.15, flaeche([hz(n) for n in akkord(grund, folge[0])], ausklang,
                                         attack=0.3, release=0.6), 0.45)

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
