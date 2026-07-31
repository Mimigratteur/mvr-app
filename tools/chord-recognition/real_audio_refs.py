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
    'emmenez_moi_vrai': {
        'status': 'TEST',
        'audio_path': '/mnt/user-data/uploads/47326-french-chanson-aznavour-emmenez-moi.mp3',
        'source': "Reprise de reference_grid.py (meme chanson, progression standard "
                  "confirmee par plusieurs tablatures concordantes)",
        'chords': ['Am', 'Em', 'Am', 'E7', 'Am', 'G', 'Am', 'E7', 'Am', 'G', 'Am', 'E7',
                   'Am', 'F', 'G', 'F', 'C', 'F', 'C', 'E7'],
        'compare_first_n_hyp': 25,
    },
    'nougaro_tu_verras': {
        'status': 'TEST',
        'audio_path': '/mnt/user-data/uploads/42628-claude-nougaro-tu-verras.mp3',
        'source': 'partoch.com #3078462, simplifie (extensions jazz ramenees a la triade de base)',
        'chords': ['Dm', 'Am', 'Gm', 'Bbm', 'Em', 'A7', 'Dm', 'Am', 'Gm', 'Bbm', 'Em', 'A7'],
        'compare_first_n_hyp': 15,
    },
    'delpech_pour_un_flirt': {
        'status': 'TEST',
        'audio_path': '/mnt/user-data/uploads/44034-delpech-michel-pour-un-flirt.mp3',
        'source': 'guitare-tabs.com + ultimate-guitar (concordants), simplifie',
        'chords': ['D', 'A', 'D', 'Bm', 'Em', 'A', 'D', 'Bm', 'Em', 'A', 'D', 'A', 'D'],
        'compare_first_n_hyp': 18,
    },
    'fugain_bravo_monsieur_le_monde': {
        'status': 'TEST',
        'audio_path': '/mnt/user-data/uploads/47511-fugain-michel-bravo-monsieur-le-monde1.mp3',
        'source': 'partoch.com #2802544, simplifie',
        'chords': ['Em', 'E7', 'Am', 'B7', 'Em', 'Am', 'B7', 'Em', 'E7', 'Am', 'B7', 'Em', 'Am', 'B7'],
        'compare_first_n_hyp': 18,
    },
    'joe_dassin_petit_pain_au_chocolat': {
        'status': 'TEST',
        'audio_path': '/mnt/user-data/uploads/51019-joe-dassin-le-petit-pain-au-chocolat.mp3',
        'source': 'chordie.com + francetabs.com (transpose en Sol, confirme par Chordify), simplifie',
        'chords': ['G', 'D', 'G', 'D', 'G', 'C', 'G', 'D', 'G', 'C', 'G', 'D', 'G'],
        'compare_first_n_hyp': 16,
    },
    'joe_dassin_siffler_sur_la_colline': {
        'status': 'TEST',
        'audio_path': '/mnt/user-data/uploads/51022-joe-dassin-siffler-sur-la-colline.mp3',
        'source': 'ultimate-guitar + Chordify (concordants : Dm,C,F,A), simplifie',
        'chords': ['Dm', 'C', 'Dm', 'C', 'Gm', 'Dm', 'C', 'Gm', 'Dm', 'A', 'F', 'C', 'A7', 'Dm'],
        'compare_first_n_hyp': 16,
    },
    'nino_ferrer_le_sud': {
        'status': 'TEST',
        'audio_path': '/mnt/user-data/uploads/54412-nino-ferrer-le-sud.mp3',
        'source': 'pascalsandrez.fr + ultimate-guitar (concordants), simplifie',
        'chords': ['C', 'Em', 'Am', 'F', 'C', 'Em', 'Am', 'F', 'Em', 'F', 'C', 'G', 'F', 'C', 'G', 'F'],
        'compare_first_n_hyp': 18,
    },
    'nougaro_armstrong': {
        'status': 'TEST',
        'confidence': 'basse - extrait automatique (Chordify PDF), pas de recoupement multi-source',
        'audio_path': '/mnt/user-data/uploads/54721-nougaro-claude-armstrong.mp3',
        'source': 'Export Chordify (PDF fourni par utilisateur), extraction texte partiellement fiable',
        'chords': ['G', 'C', 'E', 'Gm', 'Dm', 'Gm', 'Cm', 'Gm', 'C7', 'D7', 'Gm', 'Gm', 'D',
                   'Gm', 'Cm', 'Dm', 'D', 'Gm'],
        'compare_first_n_hyp': 20,
    },
    'souchon_foule_sentimentale': {
        'status': 'TEST',
        'confidence': 'basse - extrait automatique (Chordify PDF), pas de recoupement multi-source',
        'audio_path': '/mnt/user-data/uploads/57778-souchon-alain-foule-sentimentale.mp3',
        'source': 'Export Chordify (PDF fourni par utilisateur)',
        'chords': ['B7', 'Am', 'B7', 'Em', 'Am', 'D', 'Em', 'C', 'Em', 'Am', 'D', 'Em', 'C'],
        'compare_first_n_hyp': 20,
    },
    'restos_du_coeur': {
        'status': 'TEST',
        'confidence': 'basse - extrait automatique (Chordify PDF), pas de recoupement multi-source',
        'audio_path': '/mnt/user-data/uploads/52010-les-enfoires-les-restos-du-coeur.mp3',
        'source': 'Export Chordify (PDF fourni par utilisateur)',
        'chords': ['C', 'Am', 'Bm', 'Em', 'C', 'Am', 'Bm', 'B', 'C', 'Em', 'B', 'Bm', 'F',
                   'Bm', 'G', 'Bm', 'F', 'G'],
        'compare_first_n_hyp': 20,
    },
    'cocciante_coup_de_soleil': {
        'status': 'TEST',
        'confidence': 'basse - extrait automatique (Chordify PDF), pas de recoupement multi-source',
        'audio_path': '/mnt/user-data/uploads/73065-italian-cocciante-t1000-richard-cocciante-un-coup-de-soleil.mp3',
        'source': 'Export Chordify (PDF fourni par utilisateur)',
        'chords': ['D7', 'Gm', 'D', 'C', 'D7', 'Gm', 'G', 'C', 'F', 'Am', 'F', 'Am', 'D',
                   'D7', 'Gm', 'D7', 'A', 'F', 'C', 'F', 'Gm'],
        'compare_first_n_hyp': 22,
    },
    'deep_purple_smoke_on_the_water': {
        'status': 'TEST',
        'audio_path': '/mnt/user-data/uploads/Deep-Purple-Smoke-On-The-Water-v7.mp3',
        'source': 'Riff tres documente et concordant entre sources (Wikipedia, Ultimate Guitar, '
                  'chords-and-tabs.net) : joue en power chords sur guitare distordue',
        'chords': ['G5', 'Bb5', 'C5', 'G5', 'Bb5', 'Db5', 'C5', 'G5', 'Bb5', 'C5', 'Bb5', 'G5'],
        'compare_first_n_hyp': 15,
    },
    'deep_purple_black_night': {
        'status': 'TEST',
        'audio_path': '/mnt/user-data/uploads/Deep-Purple-Black-Night-v2.mp3',
        'source': 'Structure claire et concordante (themusicdept.com Rockschool + azchords.com)',
        'chords': ['E5', 'A', 'G', 'E5', 'A', 'G', 'B5'],
        'compare_first_n_hyp': 12,
    },
    # 'nom_du_morceau': {
    #     'status': 'TEST',
    #     'audio_path': '/mnt/user-data/uploads/....mp3',
    #     'source': 'où la référence a été trouvée (Chordify, Ultimate Guitar, à l'oreille, etc.)',
    #     'chords': ['Am', 'G', 'F', 'E7', ...],
    #     'compare_first_n_hyp': 20,  # ou None pour comparer toute la séquence détectée
    # },
}
