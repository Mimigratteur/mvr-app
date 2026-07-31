"""
Références d'accords pour vrais enregistrements (pas MIDI).

Format volontairement simple : pour chaque morceau, une séquence ordonnée
d'accords (pas de timing précis nécessaire - on compare par alignement de
séquence, comme pour Emmenez-moi-mimi, voir evaluate_seq.py). La séquence
peut être partielle (juste le début, ou une section connue) : la
comparaison se fait alors bornée à cette même portion de la sortie de
l'outil (voir evaluate_real.py).

IMPORTANT - calibration vs test :
Les morceaux marqués CALIBRATION ont servi à régler les seuils/poids de
l'outil (recognize_windowed, recognize_key_viterbi) le 31/07/2026. Un
score élevé dessus ne prouve pas que l'outil généralise - c'est attendu,
puisqu'on a réglé dessus. Les morceaux marqués TEST sont ceux qu'on n'a
PAS utilisés pour régler quoi que ce soit : leur score est la vraie
mesure honnête de généralisation. Ajouter de nouveaux morceaux ici comme
TEST, jamais re-régler les seuils dessus sans les faire passer en
CALIBRATION explicitement (et le dire).
"""

REFERENCES = {
    # --- CALIBRATION (ont servi à régler key_weight, stay_prob, etc.) ---
    'la_corrida': {
        'status': 'CALIBRATION',
        'audio_path': '/mnt/user-data/uploads/La_corridacomplet.mp3',
        'source': 'Grille Chordify (lue sur capture écran utilisateur, 31/07/2026)',
        'chords': ['Dm', 'Bbm', 'Bb', 'Gm', 'Dm', 'F', 'C', 'Bb', 'Dm', 'F',
                   'C', 'Bb', 'Dm', 'F', 'C'],
        'compare_first_n_hyp': 20,  # nb de segments détectés à comparer (début du morceau)
    },
    'gary_moore_still_got_the_blues': {
        'status': 'CALIBRATION',
        'audio_path': '/mnt/user-data/uploads/Gary_Moore_Still_Got_the_Blues_Playback_Personnalise_.mp3',
        'source': "Progression connue et publiée (recherche web, 31/07/2026) : "
                  "Dm7-G-Cmaj7-Fmaj7-Bm7b5-E7-Am (intro), simplifiée sans le b5",
        'chords': ['Dm7', 'G', 'Cmaj7', 'Fmaj7', 'Bm', 'E7', 'Am'],
        'compare_first_n_hyp': 15,
    },

    # --- TEST (à ajouter au fur et à mesure, ne pas re-régler dessus) ---
    # 'nom_du_morceau': {
    #     'status': 'TEST',
    #     'audio_path': '/mnt/user-data/uploads/....mp3',
    #     'source': 'où la référence a été trouvée (Chordify, Ultimate Guitar, à l'oreille, etc.)',
    #     'chords': ['Am', 'G', 'F', 'E7', ...],
    #     'compare_first_n_hyp': 20,  # ou None pour comparer toute la séquence détectée
    # },
}
