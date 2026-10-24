"""Erzeugt automatisch neue Rätsel, deren Lösung das Skript selbst ausrechnet – also garantiert stimmt.

- Emoji-Gleichungen: drei Symbole, drei Hinweis-Gleichungen, eine Frage. Bei „schwer“ steckt in
  der Frage eine Punkt-vor-Strich-Falle, und die typische Falsch-Antwort steht als Option zur Wahl.
- „Finde die 9“: ein Gitter aus gleichen Zeichen mit genau einem abweichenden.
"""

import random

EMOJI_SYMBOLE = ["🍎", "🍌", "🍒", "🍇", "🍓", "🍉", "🍋", "🍑", "🍍", "🥝", "🥥", "🍐", "🍔", "🍕",
                 "🍩", "🍪", "🧁", "🍦", "🐶", "🐱", "🐸", "🐼", "🦊", "🐵", "🐷", "🐔", "⚽", "🏀",
                 "🎈", "🎁", "⭐", "🚗"]

# Zeichenpaare (normal, abweichend) – je ähnlicher, desto schwerer
FINDE_PAARE = {
    "leicht": [("6", "9"), ("O", "Q"), ("E", "F"), ("😀", "😎"), ("🍎", "🍅")],
    "mittel": [("8", "B"), ("5", "S"), ("C", "G"), ("M", "N"), ("😐", "😑"), ("🙂", "🙃")],
    "schwer": [("O", "0"), ("B", "8"), ("Z", "2"), ("😃", "😄"), ("🐻", "🐨")],
}
FINDE_GITTER = {"leicht": (7, 7), "mittel": (8, 8), "schwer": (10, 10)}  # (Spalten, Reihen) – quadratisch nutzt den Platz am besten
SCHWIERIGKEITEN = ["leicht", "mittel", "schwer"]


def naechste_id(raetsel):
    return max((int(r["id"]) for r in raetsel), default=0) + 1


def rechne(werte, operatoren):
    """Wertet eine Rechnung mit Punkt-vor-Strich aus, z. B. ([2, 10, 4], ["+", "×"]) → 42."""
    zahlen, ops = [werte[0]], []
    for op, wert in zip(operatoren, werte[1:]):
        if op == "×":
            zahlen[-1] *= wert
        else:
            zahlen.append(wert)
            ops.append(op)
    ergebnis = zahlen[0]
    for op, wert in zip(ops, zahlen[1:]):
        ergebnis = ergebnis + wert if op == "+" else ergebnis - wert
    return ergebnis


def rechne_von_links(werte, operatoren):
    """Die typische Falsch-Rechnung: stur von links nach rechts."""
    ergebnis = werte[0]
    for op, wert in zip(operatoren, werte[1:]):
        ergebnis = ergebnis * wert if op == "×" else ergebnis + wert if op == "+" else ergebnis - wert
    return ergebnis


def zeile(symbole, operatoren):
    teile = [symbole[0]]
    for op, sym in zip(operatoren, symbole[1:]):
        teile += [op, sym]
    return " ".join(teile)


def emoji_gleichung(zufall, schwierigkeit, neue_id):
    a_sym, b_sym, c_sym = zufall.sample(EMOJI_SYMBOLE, 3)
    while True:
        a, b, c = zufall.randint(2, 9), zufall.randint(2, 9), zufall.randint(1, 8)
        if len({a, b, c}) == 3 and b > c:
            break
    wert = {a_sym: a, b_sym: b, c_sym: c}

    n = zufall.choice([2, 3])
    hinweise = [f"{zeile([a_sym] * n, ['+'] * (n - 1))} = {n * a}",
                f"{zeile([a_sym, b_sym, b_sym], ['+', '+'])} = {a + 2 * b}"]
    if schwierigkeit == "leicht":
        hinweise.append(f"{zeile([c_sym, c_sym], ['+'])} = {2 * c}")
    else:
        hinweise.append(f"{zeile([b_sym, c_sym], ['−'])} = {b - c}")

    if schwierigkeit == "leicht":
        symbole, ops = [c_sym, a_sym, b_sym], ["+", "+"]
    elif schwierigkeit == "mittel":
        symbole, ops = [a_sym, c_sym, b_sym], ["×", "+"]
    else:
        symbole, ops = [c_sym, a_sym, b_sym], ["+", "×"]  # Punkt-vor-Strich-Falle
    werte = [wert[s] for s in symbole]
    loesung = rechne(werte, ops)

    raetsel = {
        "id": neue_id,
        "kategorie": "emoji",
        "frage": "\n".join(hinweise) + f"\n*{zeile(symbole, ops)} = ?*",
        "loesung": str(loesung),
        "erklaerung": f"{a_sym} = {a}, {b_sym} = {b}, {c_sym} = {c} → {zeile([str(w) for w in werte], ops)}"
                      f" = {loesung}."
                      + (" Punkt vor Strich!" if schwierigkeit == "schwer" else ""),
        "schwierigkeit": schwierigkeit,
        "status": "neu",
    }
    if schwierigkeit == "schwer":
        falsch = rechne_von_links(werte, ops)
        dritte = sum(werte)
        if len({loesung, falsch, dritte}) < 3:
            dritte = loesung + zufall.choice([-2, 2, 10])
        if len({loesung, falsch, dritte}) == 3 and min(loesung, falsch, dritte) > 0:
            raetsel["optionen"] = [str(x) for x in sorted([loesung, falsch, dritte])]
    return raetsel


def finde_raetsel(zufall, schwierigkeit, neue_id):
    zeichen, ziel = zufall.choice(FINDE_PAARE[schwierigkeit])
    spalten, reihen = FINDE_GITTER[schwierigkeit]
    reihe, spalte = zufall.randint(2, reihen - 1), zufall.randint(2, spalten - 1)  # nie am Rand – zu leicht
    if ziel.isdigit():
        artikel = "die"
    elif ziel.isalpha():
        artikel = "das"
    else:
        artikel = "das"  # Emoji
    return {
        "id": neue_id,
        "kategorie": "finde",
        "typ": "finde",
        "frage": f"Finde {artikel} *{ziel}*!",
        "zeichen": zeichen,
        "ziel": ziel,
        "spalten": spalten,
        "zeilen": reihen,
        "position": [reihe, spalte],
        "loesung": f"Reihe {reihe}, Spalte {spalte}",
        "erklaerung": f"{artikel.capitalize()} {ziel} versteckt sich in Reihe {reihe}, Spalte {spalte}"
                      " – gezählt von oben links.",
        "schwierigkeit": schwierigkeit,
        "status": "neu",
    }


def erzeuge(art, anzahl, raetsel, schwierigkeit=None, saat=None):
    """Hängt `anzahl` neue Rätsel der Art "emoji" oder "finde" an die Liste an und gibt sie zurück."""
    zufall = random.Random(saat)
    bauer = {"emoji": emoji_gleichung, "finde": finde_raetsel}[art]
    neu = []
    for i in range(anzahl):
        stufe = schwierigkeit or SCHWIERIGKEITEN[i % len(SCHWIERIGKEITEN)]
        eintrag = bauer(zufall, stufe, naechste_id(raetsel))
        raetsel.append(eintrag)
        neu.append(eintrag)
    return neu
