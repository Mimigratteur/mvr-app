"""
Évalue chord_recognizer sur toutes les références de real_audio_refs.py,
en séparant clairement le score CALIBRATION (attendu haut, sert juste à
vérifier qu'on n'a rien cassé) du score TEST (la vraie mesure honnête de
généralisation - ce qui compte vraiment).

Usage : python3 evaluate_real.py [--method windowed|key_viterbi]
"""
import sys
from chord_recognizer import recognize_windowed, recognize_key_viterbi
from real_audio_refs import REFERENCES
from evaluate_seq import align, root_of, dedupe


def evaluate_all(method='key_viterbi', verbose=False):
    recognize_fn = recognize_key_viterbi if method == 'key_viterbi' else recognize_windowed

    for status_filter in ('CALIBRATION', 'TEST'):
        entries = {k: v for k, v in REFERENCES.items() if v['status'] == status_filter}
        if not entries:
            print(f"\n=== {status_filter} : aucune référence ===")
            continue

        print(f"\n=== {status_filter} ===")
        tot_exact, tot_root, maxtot = 0, 0, 0
        for name, ref in entries.items():
            segs, analysis = recognize_fn(ref['audio_path'])
            hyp = dedupe([s[0] for s in segs])
            n_hyp = ref.get('compare_first_n_hyp')
            if n_hyp:
                hyp = hyp[:n_hyp]
            pairs = align(ref['chords'], hyp)
            n_exact = sum(1 for r, h in pairs if r is not None and r == h)
            n_root = sum(1 for r, h in pairs if r and h and root_of(r) == root_of(h))
            n_ref = len(ref['chords'])
            tot_exact += n_exact
            tot_root += n_root
            maxtot += n_ref
            print(f"  {name:35s} exact={n_exact}/{n_ref} ({100*n_exact/n_ref:.0f}%)  "
                  f"root={n_root}/{n_ref} ({100*n_root/n_ref:.0f}%)  [{ref['source']}]")
            if verbose:
                for r, h in pairs:
                    mark = 'OK' if r == h else ('root' if r and h and root_of(r) == root_of(h) else 'X')
                    print(f"      {str(r):10s} -> {str(h):10s} [{mark}]")

        if maxtot:
            print(f"  {'TOTAL':35s} exact={tot_exact}/{maxtot} ({100*tot_exact/maxtot:.0f}%)  "
                  f"root={tot_root}/{maxtot} ({100*tot_root/maxtot:.0f}%)")


if __name__ == "__main__":
    method = 'windowed' if '--method' in sys.argv and 'windowed' in sys.argv else 'key_viterbi'
    evaluate_all(method=method, verbose='-v' in sys.argv)
