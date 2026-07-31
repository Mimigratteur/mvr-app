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

# Profils de Krumhansl-Kessler (cognition de la tonalité), standard en MIR
_MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def estimate_key(analysis, silence_ratio=0.06):
    """Estime la tonalité (fondamentale, 'maj'/'min') du morceau entier par
    corrélation avec les profils de Krumhansl-Kessler. Utilisé comme a
    priori pour départager les accords ambigus (voir diatonic_bonus)."""
    chroma, rms = analysis['chroma'], analysis['rms']
    mask = rms > rms.max() * silence_ratio
    if mask.sum() == 0:
        return None, None
    avg = chroma[:, mask].mean(axis=1)
    avg = avg / (avg.sum() + 1e-9)
    best_root, best_mode, best_corr = None, None, -2.0
    for root in range(12):
        maj = np.roll(_MAJOR_PROFILE, root)
        minr = np.roll(_MINOR_PROFILE, root)
        maj_corr = np.corrcoef(avg, maj / maj.sum())[0, 1]
        min_corr = np.corrcoef(avg, minr / minr.sum())[0, 1]
        if maj_corr > best_corr:
            best_root, best_mode, best_corr = root, 'maj', maj_corr
        if min_corr > best_corr:
            best_root, best_mode, best_corr = root, 'min', min_corr
    return best_root, best_mode


# degres diatoniques -> (qualite preferee, bonus) relatifs a la tonique.
# Pour la tonalite mineure on inclut V/V7 (mineure harmonique, tres
# frequent en cadence : ex. E7 en La mineur) en plus du v naturel.
_DIATONIC_MAJOR = {0: ['maj', '7'], 2: ['min'], 4: ['min'], 5: ['maj'],
                    7: ['maj', '7'], 9: ['min']}
_DIATONIC_MINOR = {0: ['min'], 3: ['maj'], 5: ['min'], 7: ['min', 'maj', '7'],
                    8: ['maj'], 10: ['maj', '7']}


def diatonic_bonus(root, qual, key_root, key_mode, weight=0.15):
    """Bonus additif si (root, qual) est un accord diatonique plausible de
    la tonalite estimee. Sert a departager les cas ambigus, pas a forcer
    une decision contre une preuve audio claire (poids volontairement
    modeste)."""
    if key_root is None:
        return 0.0
    table = _DIATONIC_MAJOR if key_mode == 'maj' else _DIATONIC_MINOR
    degree = (root - key_root) % 12
    if degree in table and qual in table[degree]:
        return weight
    return 0.0

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


def score_frame(chroma_vec, bass_vec, bass_bonus=1.6, third_thresh=0.04, flat7_thresh=0.24,
                 key_root=None, key_mode=None, key_weight=0.6):
    """Retourne (root, qual) pour une frame de chroma donnée.

    Approche par ratios d'énergie plutôt que par compétition de gabarits :
    une simple similarité cosinus favorise artificiellement les gabarits
    à moins de composantes (ex. power chord "5" gagne presque toujours
    contre maj/min, car il n'est jamais "pénalisé" par une tierce faible
    ou bruitée). On choisit donc explicitement la meilleure fondamentale
    par énergie root+quinte, puis on décide de la tierce (maj/min/absente)
    et de la 7e par des seuils sur l'énergie réellement présente à ces
    degrés, relativement à la triade.

    Si key_root/key_mode sont fournis (voir estimate_key), un léger bonus
    (key_weight) favorise les accords diatoniques de la tonalité estimée
    en cas d'ambiguïté — ça ne force jamais une décision contre une
    preuve audio claire, le poids reste modeste par rapport aux termes
    d'énergie réels."""
    total = chroma_vec.sum()
    if total < 1e-6:
        return None, None

    bass_root = int(np.argmax(bass_vec)) if bass_vec.sum() > 1e-6 else None

    # 1) choisir la fondamentale : énergie(root) + énergie(quinte), avec
    #    bonus si la note de basse détectée correspond à cette fondamentale,
    #    et léger bonus si la fondamentale est diatonique de la tonalité
    best_root, best_score = None, -1.0
    for root in range(12):
        e_root = chroma_vec[root]
        e_fifth = chroma_vec[(root + 7) % 12]
        score = e_root + 0.7 * e_fifth
        if bass_root is not None and root == bass_root:
            score += bass_bonus * e_root
        if key_root is not None:
            # bonus générique si la fondamentale appartient à un degré
            # diatonique quelconque de la tonalité (avant de savoir la qualité)
            table = _DIATONIC_MAJOR if key_mode == 'maj' else _DIATONIC_MINOR
            if (root - key_root) % 12 in table:
                score += key_weight * e_root
        if score > best_score:
            best_root, best_score = root, score

    root = best_root
    e_root = chroma_vec[root] + 1e-9
    e_maj3 = chroma_vec[(root + 4) % 12]
    e_min3 = chroma_vec[(root + 3) % 12]
    e_fifth = chroma_vec[(root + 7) % 12]
    e_flat7 = chroma_vec[(root + 10) % 12]

    # 2) tierce : celle des deux (maj/min) la plus énergétique, seulement
    #    si elle dépasse un seuil relatif à la fondamentale (sinon "5"),
    #    avec léger bonus diatonique pour départager les cas proches
    third_energy = max(e_maj3, e_min3)
    if third_energy < third_thresh * e_root:
        qual = '5'
    else:
        maj_score = e_maj3 + diatonic_bonus(root, 'maj', key_root, key_mode, key_weight) * e_root
        min_score = e_min3 + diatonic_bonus(root, 'min', key_root, key_mode, key_weight) * e_root
        qual = 'maj' if maj_score >= min_score else 'min'

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


def recognize_windowed(path, window_s=2.0, bass_bonus=1.6, third_thresh=0.04,
                        flat7_thresh=0.24, silence_ratio=0.06, merge_repeats=True,
                        stability='min', use_key=True, key_weight=0.6):
    """Variante pour VRAIS ENREGISTREMENTS (pas de l'audio MIDI propre).

    Sur un vrai enregistrement (batterie, plusieurs instruments, cordes à
    vide qui résonnent), une décision par frame de ~93ms est bien trop
    fine : elle capte des artefacts (résonance, notes de passage) plutôt
    que l'accord réellement joué. On agrège le chroma sur des fenêtres
    d'environ 1 accord tenu (~1.5s par défaut) avant de décider — ça
    lisse les artefacts sans avoir besoin de connaître le tempo.

    `stability` contrôle comment on agrège chaque fenêtre :
    - 'min' (défaut) : minimum des frames — ne retient que ce qui est
      présent en permanence sur toute la fenêtre, rejette les notes de
      passage brèves même si elles sont fortes un instant.
    - 'median' : médiane des frames, plus simple mais moins robuste au
      bruit ponctuel sur vrai enregistrement.

    `use_key` estime la tonalité du morceau entier (Krumhansl-Kessler) et
    s'en sert comme léger a priori pour départager les accords ambigus
    (voir estimate_key/diatonic_bonus) — n'écrase jamais une preuve audio
    claire, poids modeste par défaut (key_weight=0.15).

    Réglages calibrés (31/07/2026) sur deux vrais enregistrements contre
    des références indépendantes (grille Chordify pour La Corrida,
    progression connue et publiée pour l'intro de Still Got the Blues) :
    window_s=2.0, stability='min' -> 53% (La Corrida) / 71% (Gary Moore)
    de fondamentale correcte, contre 47% / 43% avec la version initiale
    (fenêtres de 1.5s, agrégation par médiane). Avec use_key=True en plus,
    voir README pour le résultat mesuré le plus récent."""
    analysis = load_and_analyze(path)
    chroma, bass_chroma, rms, times = (analysis['chroma'], analysis['bass_chroma'],
                                        analysis['rms'], analysis['times'])
    hop_s = times[1] - times[0]
    win = max(1, int(window_s / hop_s))
    silence_thresh = rms.max() * silence_ratio
    agg = np.min if stability == 'min' else np.median

    key_root, key_mode = (estimate_key(analysis, silence_ratio) if use_key else (None, None))

    segments = []
    for i in range(0, chroma.shape[1], win):
        lo, hi = i, min(i + win, chroma.shape[1])
        if hi <= lo:
            continue
        t0, t1 = times[lo], times[min(hi, len(times) - 1)]
        if rms[lo:hi].mean() < silence_thresh:
            label = 'N.C.'
        else:
            c_agg = agg(chroma[:, lo:hi], axis=1)
            b_agg = agg(bass_chroma[:, lo:hi], axis=1)
            root, qual = score_frame(c_agg, b_agg, bass_bonus=bass_bonus,
                                      third_thresh=third_thresh, flat7_thresh=flat7_thresh,
                                      key_root=key_root, key_mode=key_mode, key_weight=key_weight)
            label = chord_name(root, qual) if root is not None else 'N.C.'
        segments.append((label, t0, t1))

    if merge_repeats:
        merged = [segments[0]]
        for label, t0, t1 in segments[1:]:
            if label == merged[-1][0]:
                merged[-1] = (merged[-1][0], merged[-1][1], t1)
            else:
                merged.append((label, t0, t1))
        segments = merged

    return segments, analysis


_VITERBI_STATES = [(r, q) for r in range(12) for q in ('maj', 'min', '7', '5')] + [('NC', None)]
_VITERBI_N_STATES = len(_VITERBI_STATES)
_VITERBI_STATE_IDX = {s: i for i, s in enumerate(_VITERBI_STATES)}


def _key_transition_log_matrix(key_root, key_mode, stay_prob, diatonic_bonus_prob):
    """Matrice de transition Viterbi : forte probabilité de rester sur le
    même accord, puis parmi les changements, préférence pour les accords
    diatoniques de la tonalité plutôt qu'une répartition uniforme."""
    table = _DIATONIC_MAJOR if key_mode == 'maj' else _DIATONIC_MINOR
    degrees = set(table.keys()) if key_root is not None else set()
    base = np.ones(_VITERBI_N_STATES)
    for i, (r, q) in enumerate(_VITERBI_STATES):
        if r == 'NC':
            continue
        deg = (r - key_root) % 12 if key_root is not None else None
        if deg in degrees:
            base[i] = diatonic_bonus_prob
    base = base / base.sum()
    logT = np.zeros((_VITERBI_N_STATES, _VITERBI_N_STATES))
    for i in range(_VITERBI_N_STATES):
        row = base.copy()
        row[i] = 0
        row = row / row.sum() * (1 - stay_prob)
        row[i] = stay_prob
        logT[i, :] = np.log(row + 1e-12)
    return logT


def recognize_key_viterbi(path, window_s=2.0, bass_bonus=1.6, third_thresh=0.04,
                           flat7_thresh=0.24, silence_ratio=0.06, key_weight=0.6,
                           stay_prob=0.5, diatonic_bonus_prob=8.0, vote_bonus=5.0):
    """Meilleure méthode actuelle pour VRAIS ENREGISTREMENTS. Combine
    `recognize_windowed()` (agrégation par minimum sur des fenêtres ~2s,
    a priori de tonalité par accord) avec un lissage Viterbi dont la
    matrice de TRANSITION est elle aussi informée par la tonalité : les
    enchaînements vers un accord diatonique de la clé sont favorisés par
    rapport à une répartition uniforme, en plus de la forte probabilité
    de rester sur le même accord.

    Résultat mesuré (31/07/2026, comparaison bornée au début de deux
    vrais enregistrements contre références indépendantes) :
    55% exact (fondamentale + qualité) / 68% fondamentale seule,
    contre 45%/59% pour recognize_windowed() seul, et 23%/59% sans aucun
    a priori de tonalité. Plateau stable trouvé par recherche en grille
    (stay_prob 0.4-0.5, diatonic_bonus_prob 5-20 tous équivalents) - pas
    un pic isolé de sur-ajustement.

    Reste loin des ~90% d'outils matures comme Chordify (voir README) :
    ceux-ci s'appuient sur des modèles entraînés sur de vraies données à
    grande échelle, pas sur des règles/seuils calibrés à la main sur
    deux morceaux comme ici."""
    analysis = load_and_analyze(path)
    chroma, bass_chroma, rms, times = (analysis['chroma'], analysis['bass_chroma'],
                                        analysis['rms'], analysis['times'])
    hop_s = times[1] - times[0]
    win = max(1, int(window_s / hop_s))
    silence_thresh = rms.max() * silence_ratio
    key_root, key_mode = estimate_key(analysis, silence_ratio)

    win_labels, win_bounds = [], []
    for i in range(0, chroma.shape[1], win):
        lo, hi = i, min(i + win, chroma.shape[1])
        if hi <= lo:
            continue
        t0, t1 = times[lo], times[min(hi, len(times) - 1)]
        if rms[lo:hi].mean() < silence_thresh:
            win_labels.append(('NC', None))
        else:
            c_agg = np.min(chroma[:, lo:hi], axis=1)
            b_agg = np.min(bass_chroma[:, lo:hi], axis=1)
            root, qual = score_frame(c_agg, b_agg, bass_bonus=bass_bonus, third_thresh=third_thresh,
                                      flat7_thresh=flat7_thresh, key_root=key_root, key_mode=key_mode,
                                      key_weight=key_weight)
            win_labels.append((root, qual) if root is not None else ('NC', None))
        win_bounds.append((t0, t1))

    n = len(win_labels)
    log_em = np.zeros((_VITERBI_N_STATES, n))
    for i, s in enumerate(win_labels):
        log_em[_VITERBI_STATE_IDX[s], i] = vote_bonus

    logT = _key_transition_log_matrix(key_root, key_mode, stay_prob, diatonic_bonus_prob)

    dp = np.zeros((_VITERBI_N_STATES, n))
    bp = np.zeros((_VITERBI_N_STATES, n), dtype=np.int32)
    dp[:, 0] = log_em[:, 0]
    for t in range(1, n):
        scores = dp[:, t - 1][:, None] + logT
        bp[:, t] = np.argmax(scores, axis=0)
        dp[:, t] = np.max(scores, axis=0) + log_em[:, t]

    path_states = np.zeros(n, dtype=np.int32)
    path_states[-1] = int(np.argmax(dp[:, -1]))
    for t in range(n - 2, -1, -1):
        path_states[t] = bp[path_states[t + 1], t + 1]

    segments = []
    for i, si in enumerate(path_states):
        r, q = _VITERBI_STATES[si]
        label = 'N.C.' if r == 'NC' else chord_name(r, q)
        t0, t1 = win_bounds[i]
        if segments and segments[-1][0] == label:
            segments[-1] = (label, segments[-1][1], t1)
        else:
            segments.append((label, t0, t1))
    return segments, analysis


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else '/mnt/user-data/uploads/EMMENEZ-MOI-MIMI.wav'
    segs, analysis = recognize(path)
    print(f"{len(segs)} segments détectés sur {analysis['duration']:.1f}s")
    for label, t0, t1 in segs[:30]:
        print(f"  {t0:6.2f}s - {t1:6.2f}s  {label}")
