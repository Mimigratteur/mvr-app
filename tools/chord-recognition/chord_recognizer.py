"""
chord_recognizer.py — Reconnaissance d'accords à partir d'un fichier audio.
Outil autonome, indépendant de MVR.

Méthode :
1. Chromagramme CQT (avec correction de justesse/tuning).
2. Chroma "basse" séparé (registre grave uniquement) pour identifier la
   fondamentale réellement jouée à la basse.
3. Choix de la fondamentale par énergie (root + quinte, avec bonus basse),
   puis décision maj / min / 7 (dominante) / 5 (power chord) par seuils sur
   les ratios d'énergie réels des degrés concernés (tierce, 7e mineure) —
   pas de similarité cosinus par gabarits : ça favorise artificiellement
   les gabarits à moins de composantes (voir score_frame).
4. Détection du silence (N.C.) par énergie RMS.
5. Lissage temporel (vote majoritaire glissant) puis segmentation en
   plages d'accords stables.
"""

import numpy as np
import librosa

NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def chord_name(root, qual):
    r = NOTES[root]
    if qual == 'maj':
        return r
    if qual == 'min':
        return r + 'm'
    if qual == '7':
        return r + '7'
    if qual == '5':
        return r + '5'
    return r + qual


def load_and_analyze(path, hop_length=2048, sr=22050):
    y, sr = librosa.load(path, sr=sr, mono=True)

    # correction de justesse (tuning) avant extraction du chromagramme
    tuning = librosa.estimate_tuning(y=y, sr=sr)

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length,
                                         tuning=tuning, fmin=librosa.note_to_hz('C2'))
    # chroma "basse" : uniquement le registre grave (C2-C3) pour extraire
    # la fondamentale réellement jouée à la basse, séparément de l'accord
    # complet (qui peut être dominé par des harmoniques plus aiguës)
    bass_chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length,
                                              tuning=tuning,
                                              fmin=librosa.note_to_hz('C2'),
                                              n_octaves=2)

    rms = librosa.feature.rms(y=y, frame_length=hop_length * 2, hop_length=hop_length)[0]
    times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=hop_length)

    return {
        'chroma': chroma, 'bass_chroma': bass_chroma, 'rms': rms,
        'times': times, 'sr': sr, 'duration': len(y) / sr,
    }


def score_frame(chroma_vec, bass_vec, bass_bonus=1.6, third_thresh=0.04, flat7_thresh=0.24):
    """Retourne (root, qual) pour une frame de chroma donnée.

    Approche par ratios d'énergie plutôt que par compétition de gabarits :
    une simple similarité cosinus favorise artificiellement les gabarits
    à moins de composantes (ex. power chord "5" gagne presque toujours
    contre maj/min, car il n'est jamais "pénalisé" par une tierce faible
    ou bruitée). On choisit donc explicitement la meilleure fondamentale
    par énergie root+quinte, puis on décide de la tierce (maj/min/absente)
    et de la 7e par des seuils sur l'énergie réellement présente à ces
    degrés, relativement à la triade.
    """
    total = chroma_vec.sum()
    if total < 1e-6:
        return None, None

    bass_root = int(np.argmax(bass_vec)) if bass_vec.sum() > 1e-6 else None

    # 1) choisir la fondamentale : énergie(root) + énergie(quinte), avec
    #    bonus si la note de basse détectée correspond à cette fondamentale
    best_root, best_score = None, -1.0
    for root in range(12):
        e_root = chroma_vec[root]
        e_fifth = chroma_vec[(root + 7) % 12]
        score = e_root + 0.7 * e_fifth
        if bass_root is not None and root == bass_root:
            score += bass_bonus * e_root
        if score > best_score:
            best_root, best_score = root, score

    root = best_root
    e_root = chroma_vec[root] + 1e-9
    e_maj3 = chroma_vec[(root + 4) % 12]
    e_min3 = chroma_vec[(root + 3) % 12]
    e_fifth = chroma_vec[(root + 7) % 12]
    e_flat7 = chroma_vec[(root + 10) % 12]

    # 2) tierce : celle des deux (maj/min) la plus énergétique, seulement
    #    si elle dépasse un seuil relatif à la fondamentale (sinon "5")
    third_energy = max(e_maj3, e_min3)
    if third_energy < third_thresh * e_root:
        qual = '5'
    elif e_maj3 >= e_min3:
        qual = 'maj'
    else:
        qual = 'min'

    # 3) septième dominante : seulement pour un accord majeur avec 7e
    #    mineure clairement présente
    if qual == 'maj' and e_flat7 > flat7_thresh * e_root and e_flat7 > chroma_vec[(root + 11) % 12]:
        qual = '7'

    return root, qual


def frame_level_labels(analysis, silence_ratio=0.06, bass_bonus=1.6,
                        third_thresh=0.04, flat7_thresh=0.24):
    chroma, bass_chroma, rms = analysis['chroma'], analysis['bass_chroma'], analysis['rms']
    n = chroma.shape[1]
    silence_thresh = rms.max() * silence_ratio
    labels = []
    for i in range(n):
        if rms[i] < silence_thresh:
            labels.append('N.C.')
            continue
        root, qual = score_frame(chroma[:, i], bass_chroma[:, i], bass_bonus=bass_bonus,
                                  third_thresh=third_thresh, flat7_thresh=flat7_thresh)
        labels.append(chord_name(root, qual) if root is not None else 'N.C.')
    return labels


def median_smooth_labels(labels, window=9):
    """Lissage par vote majoritaire glissant (pas une vraie médiane car
    catégoriel), pour supprimer les basculements d'un frame isolé."""
    n = len(labels)
    half = window // 2
    out = []
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        window_labels = labels[lo:hi]
        vals, counts = np.unique(window_labels, return_counts=True)
        out.append(vals[np.argmax(counts)])
    return out


def segments_from_labels(labels, times):
    """Fusionne les labels frame-level identiques et consécutifs en segments
    (accord, t_debut, t_fin)."""
    segments = []
    cur_label = labels[0]
    cur_start = times[0]
    for i in range(1, len(labels)):
        if labels[i] != cur_label:
            segments.append((cur_label, cur_start, times[i]))
            cur_label = labels[i]
            cur_start = times[i]
    segments.append((cur_label, cur_start, times[-1]))
    return segments


def recognize(path, smooth_window=3, min_segment_s=0.25, bass_bonus=1.6,
              third_thresh=0.04, flat7_thresh=0.24):
    analysis = load_and_analyze(path)
    raw_labels = frame_level_labels(analysis, bass_bonus=bass_bonus,
                                     third_thresh=third_thresh, flat7_thresh=flat7_thresh)
    smoothed = median_smooth_labels(raw_labels, window=smooth_window)
    segments = segments_from_labels(smoothed, analysis['times'])

    # fusionner les segments trop courts (bruit résiduel) avec le voisin
    # le plus proche en durée
    merged = []
    for seg in segments:
        label, t0, t1 = seg
        if merged and (t1 - t0) < min_segment_s:
            # rattacher au segment précédent plutôt que de créer un micro-segment
            prev_label, prev_t0, _ = merged[-1]
            merged[-1] = (prev_label, prev_t0, t1)
        else:
            merged.append(seg)
    return merged, analysis


def recognize_viterbi(path, bass_bonus=1.6, third_thresh=0.04, flat7_thresh=0.24,
                       vote_bonus=8.0, stay_prob=0.99, silence_ratio=0.06):
    """Variante avec lissage global par HMM/Viterbi plutôt que par vote
    majoritaire à fenêtre fixe glissante.

    Émission : on garde le classifieur par ratios d'énergie déjà calibré
    (score_frame) — il donne, par frame, un "vote" fort pour l'état choisi.
    Transition : forte probabilité de rester sur le même accord (les
    accords tiennent plusieurs temps), le reste réparti uniformément.
    Résultat mesuré (Emmenez-moi-mimi) : 85.2% exact / 99.3% fondamentale,
    contre 83.7% / 99.3% pour `recognize()` — léger gain, mais PAS de
    réduction de la sur-segmentation (349 segments contre 304)."""
    import numpy as np

    analysis = load_and_analyze(path)
    chroma, bass_chroma, rms = analysis['chroma'], analysis['bass_chroma'], analysis['rms']
    times = analysis['times']
    n = chroma.shape[1]
    silence_thresh = rms.max() * silence_ratio

    states = [(r, q) for r in range(12) for q in ('maj', 'min', '7', '5')] + [('NC', None)]
    n_states = len(states)
    state_index = {s: i for i, s in enumerate(states)}

    log_em = np.zeros((n_states, n))
    for i in range(n):
        if rms[i] < silence_thresh:
            log_em[state_index[('NC', None)], i] = vote_bonus
            continue
        root, qual = score_frame(chroma[:, i], bass_chroma[:, i], bass_bonus=bass_bonus,
                                  third_thresh=third_thresh, flat7_thresh=flat7_thresh)
        if root is None:
            log_em[state_index[('NC', None)], i] = vote_bonus
        else:
            log_em[state_index[(root, qual)], i] = vote_bonus

    log_stay = np.log(stay_prob)
    log_move = np.log((1 - stay_prob) / (n_states - 1))

    dp = np.zeros((n_states, n))
    bp = np.zeros((n_states, n), dtype=np.int32)
    dp[:, 0] = log_em[:, 0]
    for t in range(1, n):
        prev = dp[:, t - 1]
        best_idx = int(np.argmax(prev))
        best_val = prev[best_idx]
        prev_copy = prev.copy()
        prev_copy[best_idx] = -np.inf
        second_idx = int(np.argmax(prev_copy))
        second_val = prev_copy[second_idx]
        for j in range(n_states):
            stay_score = prev[j] + log_stay
            if j == best_idx:
                alt, alt_idx = second_val + log_move, second_idx
            else:
                alt, alt_idx = best_val + log_move, best_idx
            if stay_score >= alt:
                dp[j, t], bp[j, t] = stay_score + log_em[j, t], j
            else:
                dp[j, t], bp[j, t] = alt + log_em[j, t], alt_idx

    path_states = np.zeros(n, dtype=np.int32)
    path_states[-1] = int(np.argmax(dp[:, -1]))
    for t in range(n - 2, -1, -1):
        path_states[t] = bp[path_states[t + 1], t + 1]

    labels = []
    for si in path_states:
        root, qual = states[si]
        labels.append('N.C.' if root == 'NC' else chord_name(root, qual))

    segments = segments_from_labels(labels, times)
    return segments, analysis


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else '/mnt/user-data/uploads/EMMENEZ-MOI-MIMI.wav'
    segs, analysis = recognize(path)
    print(f"{len(segs)} segments détectés sur {analysis['duration']:.1f}s")
    for label, t0, t1 in segs[:30]:
        print(f"  {t0:6.2f}s - {t1:6.2f}s  {label}")
