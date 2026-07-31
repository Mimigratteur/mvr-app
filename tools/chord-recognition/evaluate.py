"""
Compare la sortie du reconnaisseur à la grille de référence (issue du MIDI),
temps par temps (78 BPM effectif, calibré sur la durée réelle de l'audio).
Donne un taux de réussite honnête + le détail des confusions.
"""

import sys
import numpy as np
from reference_grid import timed_chords
from chord_recognizer import recognize, frame_level_labels, median_smooth_labels, load_and_analyze

AUDIO_PATH = '/mnt/user-data/uploads/EMMENEZ-MOI-MIMI.wav'

ROOT_ALIASES = {'A5': 'A', 'A#5': 'A#', 'B5': 'B', 'C5': 'C', 'C#5': 'C#', 'D5': 'D',
                'D#5': 'D#', 'E5': 'E', 'F5': 'F', 'F#5': 'F#', 'G5': 'G', 'G#5': 'G#'}


def normalize_ref(chord):
    """Normalise un accord de référence pour comparaison (garde qualité)."""
    if chord == 'N.C.':
        return 'N.C.'
    return chord  # déjà sous forme "Am", "E7", "A5", "G", etc.


def root_of(chord):
    if chord in ('N.C.',):
        return None
    for suf in ('m7', '7', 'm', '5'):
        if chord.endswith(suf):
            return chord[: -len(suf)]
    return chord


def predicted_label_at(times, labels, t):
    idx = np.searchsorted(times, t, side='right') - 1
    idx = max(0, min(idx, len(labels) - 1))
    return labels[idx]


def evaluate(smooth_window=9, silence_ratio=0.06, verbose=False):
    analysis = load_and_analyze(AUDIO_PATH)
    raw = frame_level_labels(analysis)
    # patch silence_ratio dynamically if needed (frame_level_labels uses default);
    smoothed = median_smooth_labels(raw, window=smooth_window)
    times = analysis['times']

    ref = timed_chords()
    n_exact = 0
    n_root = 0
    n_total = 0
    confusions = []

    for chord, t0, t1 in ref:
        tmid = (t0 + t1) / 2
        pred = predicted_label_at(times, smoothed, tmid)
        ref_norm = normalize_ref(chord)
        n_total += 1
        exact = (pred == ref_norm)
        root_match = (root_of(pred) == root_of(ref_norm))
        if exact:
            n_exact += 1
        if root_match:
            n_root += 1
        if not exact:
            confusions.append((t0, t1, ref_norm, pred))

    print(f"Segments de référence évalués : {n_total}")
    print(f"Exact (accord + qualité)       : {n_exact}/{n_total}  ({100*n_exact/n_total:.1f}%)")
    print(f"Fondamentale correcte seule    : {n_root}/{n_total}  ({100*n_root/n_total:.1f}%)")

    if verbose:
        print("\n--- Confusions (référence -> prédit) ---")
        for t0, t1, r, p in confusions:
            print(f"  {t0:6.1f}s-{t1:6.1f}s  {r:6s} -> {p}")

    return n_exact / n_total, n_root / n_total, confusions


if __name__ == "__main__":
    verbose = '-v' in sys.argv
    evaluate(verbose=verbose)
