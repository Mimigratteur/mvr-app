from reference_grid import chord_sequence
from chord_recognizer import load_and_analyze, frame_level_labels, median_smooth_labels, \
    segments_from_labels
from evaluate_seq import align, root_of, dedupe

AUDIO_PATH = '/mnt/user-data/uploads/EMMENEZ-MOI-MIMI.wav'

analysis = load_and_analyze(AUDIO_PATH)
ref = chord_sequence()

best = None
results = []
for third_thresh in [0.0, 0.04, 0.08]:
    for flat7_thresh in [0.20, 0.24, 0.28, 0.32]:
        bass_bonus = 1.6
        raw = frame_level_labels(analysis, bass_bonus=bass_bonus,
                                  third_thresh=third_thresh, flat7_thresh=flat7_thresh)
        for smooth_window in [7, 11, 15, 21, 27]:
            sm = median_smooth_labels(raw, window=smooth_window)
            segs = segments_from_labels(sm, analysis['times'])
            for min_seg in [0.35, 0.5, 0.7, 0.9]:
                merged = []
                for seg in segs:
                    label, t0, t1 = seg
                    if merged and (t1 - t0) < min_seg:
                        prev_label, prev_t0, _ = merged[-1]
                        merged[-1] = (prev_label, prev_t0, t1)
                    else:
                        merged.append(seg)
                hyp = dedupe([s[0] for s in merged])
                pairs = align(ref, hyp)
                n_exact = sum(1 for r, h in pairs if r is not None and r == h)
                n_root = sum(1 for r, h in pairs if r and h and root_of(r) == root_of(h))
                score = n_exact + 0.3 * n_root - 0.05 * abs(len(hyp) - len(ref))
                results.append((score, n_exact, n_root, len(hyp), third_thresh, flat7_thresh, bass_bonus, smooth_window, min_seg))

results.sort(reverse=True)
print("score  exact  root  n_hyp  third_th  flat7_th  bass_bonus  smooth_w  min_seg")
for r in results[:20]:
    score, n_exact, n_root, n_hyp, tt, ft, bb, sw, ms = r
    print(f"{score:6.2f}  {n_exact:5d}  {n_root:4d}  {n_hyp:5d}   {tt:.2f}      {ft:.2f}     {bb:.1f}         {sw:3d}      {ms:.2f}")
