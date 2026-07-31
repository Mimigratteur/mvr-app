"""
Référence exacte (issue du MIDI, via export PDF MVR) pour "Emmenez-moi-mimi".
Signature 4/4, 65 BPM constant (indiqué dans le PDF : "au tempo detecté depuis l'audio").

Chaque mesure = liste de (accord, durée_en_temps).
Règle de répartition par défaut (pas d'annotation) : 4 temps divisés également
entre les accords de la mesure (1 accord=4, 2 accords=2+2, 4 accords=1+1+1+1).
Quand ce n'est pas divisible (3 accords, ou irrégulier), la grille annote
explicitement "(n)". Un cas non annoté à 3 accords ("Am E Am", début section H)
est traité par analogie avec le motif identique annoté ailleurs (Am(2) E7(1) Am(1))
=> Am(2) E(1) Am(1). C'est une hypothèse, signalée ici.

N.C. = pas d'accord (silence / percussion).
"""

SECTIONS = [
    # Section A - 8 mesures
    [
        [("Am", 2), ("Em", 2)],
        [("Am", 2), ("E7", 2)],
        [("Am", 2), ("G", 2)],
        [("Am", 2), ("E7", 2)],
        [("Am", 2), ("G", 2)],
        [("Am", 2), ("E7", 1), ("Am", 1)],
        [("F", 1), ("G", 1), ("F", 1), ("G", 1)],
        [("F", 2), ("C", 2)],
    ],
    # Section B - 9 mesures
    [
        [("C", 1), ("F", 1), ("C", 1), ("F", 1)],
        [("C", 2), ("E7", 2)],
        [("Am", 2), ("G", 2)],
        [("Am", 2), ("E7", 2)],
        [("Am", 2), ("G", 2)],
        [("Am", 4)],
        [("Am", 2), ("G", 2)],
        [("C", 1), ("G", 1), ("C", 2)],   # "C G C" non annoté, 3 tokens -> hypothèse 1+1+2
        [("E7", 1), ("Am", 2)],            # mesure irrégulière (3 temps), fin de section
    ],
    # Section C - 9 mesures
    [
        [("Am", 1), ("E", 1), ("A5", 2)],  # "Am E A5" non annoté -> hypothèse 1+1+2
        [("Am", 2), ("G", 2)],
        [("Am", 2), ("E", 2)],
        [("Am", 2), ("G", 2)],
        [("Am", 2), ("E7", 1), ("Am", 1)],
        [("F", 1), ("G", 1), ("F", 1), ("G", 1)],
        [("F", 2), ("C", 2)],
        [("F", 4)],
        [("C", 2), ("E7", 2)],
    ],
    # Section D - 11 mesures
    [
        [("Am", 2), ("G", 2)],
        [("Am", 2), ("E7", 2)],
        [("Am", 2), ("G", 2)],
        [("Am", 4)],
        [("G", 4)],
        [("C", 4)],
        [("G", 4)],
        [("C", 4)],
        [("E7", 4)],
        [("Am", 4)],
        [("E", 4)],
    ],
    # Section E - 11 mesures
    [
        [("Am", 4)],
        [("Am", 4)],
        [("G", 4)],
        [("Am", 4)],
        [("E7", 4)],
        [("Am", 4)],
        [("G", 4)],
        [("Am", 4)],
        [("E7", 2), ("Am", 2)],
        [("F", 2), ("G", 2)],
        [("F", 2), ("G", 2)],
    ],
    # Section F - 11 mesures
    [
        [("F", 4)],
        [("C", 4)],
        [("F", 4)],
        [("C", 2), ("F", 2)],
        [("C", 4)],
        [("E7", 4)],
        [("Am", 4)],
        [("G", 4)],
        [("Am", 4)],
        [("E7", 4)],
        [("Am", 4)],
    ],
    # Section G - 11 mesures
    [
        [("G", 4)],
        [("Am", 4)],
        [("Am", 4)],
        [("G", 2), ("C", 2)],
        [("G", 4)],
        [("C", 2), ("E7", 2)],
        [("Am", 2), ("E", 1)],             # mesure irrégulière (3 temps), MILIEU de section
        [("Am", 4)],
        [("G", 2), ("C", 2)],
        [("G", 2), ("C", 2)],
        [("E7", 2), ("Am", 1)],            # mesure irrégulière (3 temps), fin de section
    ],
    # Section H - 8 mesures
    [
        [("Am", 2), ("E", 1), ("Am", 1)],  # "Am E Am" non annoté -> hypothèse par analogie (2-1-1)
        [("G", 2), ("C", 2)],
        [("G", 2), ("C", 2)],
        [("E7", 2), ("Am", 2)],
        [("Am", 2), ("E", 1), ("Am", 1)],
        [("G", 2), ("C", 2)],
        [("G", 2), ("C", 2)],
        [("E", 2), ("N.C.", 1)],           # mesure irrégulière (3 temps), FIN DU MORCEAU
    ],
]

AUDIO_DURATION_S = 236.90721088435373  # mesurée sur EMMENEZ-MOI-MIMI.wav

# ATTENTION : le "65 BPM" affiché dans le PDF est une estimation MVR
# ("tempo detecté depuis l'audio"), pas le tempo réel du rendu MIDI.
# 308 temps de contenu / 236.907s d'audio (sans silence d'intro, vérifié
# par RMS) => tempo réel ~78.0 BPM. librosa.beat.beat_track sur l'audio
# brut renvoie 97.5 BPM (= 78 * 5/4) : un cas typique de confusion de
# niveau métrique (pouls détecté sur la mauvaise subdivision), le genre
# d'erreur que MVR corrige déjà pour le cas "valse". On calibre donc le
# temps directement sur la durée réelle de l'audio et le nombre de temps
# de la grille de référence, plutôt que sur le BPM affiché.
TEMPO_BPM = 78.0
BEAT_SECONDS = AUDIO_DURATION_S / 308.0  # calibration empirique (~0.7692s/temps)


def flat_beats():
    """Retourne la liste plate [(accord, nb_temps), ...] dans l'ordre du morceau."""
    out = []
    for section in SECTIONS:
        for measure in section:
            out.extend(measure)
    return out


def timed_chords(start_offset_beats=0.0):
    """Retourne [(accord, t_debut_s, t_fin_s), ...] à partir du tempo constant."""
    out = []
    t_beats = start_offset_beats
    for chord, nbeats in flat_beats():
        t0 = t_beats * BEAT_SECONDS
        t1 = (t_beats + nbeats) * BEAT_SECONDS
        out.append((chord, t0, t1))
        t_beats += nbeats
    return out


def chord_sequence():
    """Séquence ordonnée des accords sans les durées (pour alignement séquentiel)."""
    return [c for c, _ in flat_beats()]


if __name__ == "__main__":
    beats = flat_beats()
    total_beats = sum(b for _, b in beats)
    n_measures = sum(len(s) for s in SECTIONS)
    print(f"Sections : {len(SECTIONS)}  |  Mesures : {n_measures}  |  Accords (segments) : {len(beats)}")
    print(f"Total temps : {total_beats}  ->  durée théorique : {total_beats * BEAT_SECONDS:.1f}s "
          f"({total_beats * BEAT_SECONDS / 60:.2f} min)")
    irregular = [(i, c, n) for i, (c, n) in enumerate(beats)]
    # afficher les mesures irrégulières
    idx = 0
    for si, section in enumerate(SECTIONS):
        for mi, measure in enumerate(section):
            s = sum(n for _, n in measure)
            if s != 4:
                print(f"  Mesure irrégulière : section {si+1}, mesure {mi+1} -> {measure} (somme={s})")
