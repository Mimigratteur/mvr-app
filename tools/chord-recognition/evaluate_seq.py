"""
Évaluation par alignement de séquence : compare la séquence d'accords
détectée par le reconnaisseur (segmentation indépendante, basée sur les
instants réels détectés dans l'audio) à la séquence d'accords de la
référence (grille MIDI), SANS dépendre d'un calage temporel absolu exact.

C'est plus honnête que de sampler à des timestamps calculés, car nos
hypothèses de répartition des temps par mesure (2+2, etc.) ne sont pas
garanties exactes note à note.
"""

import sys
import numpy as np
from reference_grid import chord_sequence
from chord_recognizer import recognize, recognize_viterbi

AUDIO_PATH = '/mnt/user-data/uploads/EMMENEZ-MOI-MIMI.wav'


def root_of(chord):
    if chord == 'N.C.':
        return None
    for suf in ('m7', '7', 'm', '5'):
        if chord.endswith(suf):
            return chord[: -len(suf)]
    return chord


def match_score(a, b):
    if a == b:
        return 2
    if root_of(a) == root_of(b) and root_of(a) is not None:
        return 1
    return -1


GAP = -1


def align(ref, hyp):
    """Alignement global (Needleman-Wunsch) entre la séquence de référence
    et la séquence détectée (indépendante, dédupliquée)."""
    n, m = len(ref), len(hyp)
    dp = np.zeros((n + 1, m + 1))
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + GAP
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + GAP
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diag = dp[i - 1][j - 1] + match_score(ref[i - 1], hyp[j - 1])
            up = dp[i - 1][j] + GAP
            left = dp[i][j - 1] + GAP
            dp[i][j] = max(diag, up, left)

    # backtrace
    i, j = n, m
    pairs = []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + match_score(ref[i - 1], hyp[j - 1]):
            pairs.append((ref[i - 1], hyp[j - 1]))
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + GAP:
            pairs.append((ref[i - 1], None))
            i -= 1
        else:
            pairs.append((None, hyp[j - 1]))
            j -= 1
    pairs.reverse()
    return pairs


def dedupe(seq):
    out = []
    for s in seq:
        if not out or out[-1] != s:
            out.append(s)
    return out


def evaluate(verbose=False, use_viterbi=False):
    ref = chord_sequence()
    segs, analysis = (recognize_viterbi(AUDIO_PATH) if use_viterbi else recognize(AUDIO_PATH))
    hyp = dedupe([s[0] for s in segs])

    pairs = align(ref, hyp)

    n_exact = sum(1 for r, h in pairs if r is not None and r == h)
    n_root = sum(1 for r, h in pairs if r is not None and h is not None and root_of(r) == root_of(h))
    n_ref = len(ref)

    print(f"Référence : {n_ref} accords (segments)  |  Détecté : {len(hyp)} segments (dédupliqués)")
    print(f"Exact (accord + qualité) : {n_exact}/{n_ref}  ({100*n_exact/n_ref:.1f}%)")
    print(f"Fondamentale correcte    : {n_root}/{n_ref}  ({100*n_root/n_ref:.1f}%)")

    if verbose:
        print("\n--- Alignement détaillé (réf -> détecté) ---")
        for r, h in pairs:
            mark = "OK" if r == h else ("root" if r and h and root_of(r) == root_of(h) else "X")
            print(f"  {str(r):8s} -> {str(h):8s}   [{mark}]")

    return n_exact / n_ref, n_root / n_ref, pairs


if __name__ == "__main__":
    evaluate(verbose='-v' in sys.argv, use_viterbi='--viterbi' in sys.argv)
