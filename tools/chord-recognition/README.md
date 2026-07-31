# Reconnaissance d'accords — outil autonome (hors MVR)

Outil Python independant pour extraire une grille d'accords depuis un fichier audio. Volontairement hors de MVR : MVR est une PWA 100% navigateur (pas de serveur), et cet outil sert a isoler et resoudre le probleme de reconnaissance avant tout portage eventuel - meme logique que la decision prise pour l'import .gp3/.gp4/.gp5 (Python en outil de conversion externe, jamais embarque dans l'app).

## Installation

pip install librosa numpy scipy soundfile

## Utilisation

- Reconnaissance sur un fichier audio, affiche les segments detectes :
  python3 chord_recognizer.py mon_morceau.wav

- Evaluer contre la reference "Emmenez-moi-mimi" (voir reference_grid.py) :
  python3 evaluate_seq.py -v          -> alignement de sequence, methode fiable, detail des erreurs
  python3 evaluate_seq.py -v --viterbi -> meme evaluation avec le lissage HMM/Viterbi
  python3 evaluate.py -v              -> evaluation par timestamps absolus (moins fiable, voir limites plus bas)

- Recalibrer les seuils de decision (recherche en grille) :
  python3 tune.py

## Audio reel (pas MIDI) - premiers tests (31/07/2026, apres-midi)

Teste pour la premiere fois sur de vrais enregistrements (batterie,
plusieurs instruments, reverb) : La Corrida (Cabrel) et Still Got the
Blues (Gary Moore). recognize() et recognize_viterbi() (calibres sur
audio MIDI propre) echouent completement dessus : decisions par frame de
93ms bien trop fines, elles captent des artefacts de vrai enregistrement
(cordes a vide qui resonnent, notes de passage) plutot que l'accord
reellement joue - jusqu'a 540 segments detectes pour un morceau qui n'en
a raisonnablement pas plus d'une centaine.

Piste testee avec succes partiel : recognize_windowed(), qui agrege le
chroma par mediane sur des fenetres ~1.5s (environ la duree d'un accord
tenu) avant de decider, au lieu de trancher quasi instantanement. Ca fait
tomber La Corrida de 540 a 176 segments, avec une progression stable et
plausible sur les passages simples (intro). Sur Still Got the Blues
(morceau connu en La mineur), Am domine tres largement la sequence
detectee, coherent avec la tonalite reelle. Les passages plus denses
(plusieurs instruments simultanes) restent bruites.

Important : separation harmonique/percussive (librosa HPSS) testee et
n'a presque rien change - le probleme n'est pas le bruit de batterie
mais la richesse d'un vrai mixage. Bibliotheque pre-entrainee autochord
testee mais inutilisable dans cet environnement (modele Google Drive
inaccessible), et n'annonce de toute facon que 67% sur 25 accords tres
simples meme dans de bonnes conditions.

recognize_windowed() n'a pas de chiffre de reussite mesure (pas de
reference connue pour ces morceaux, contrairement a Emmenez-moi-mimi) -
c'est un point de depart a corriger a l'oreille, pas encore un resultat
valide comme les 83.7%/85.2% sur audio MIDI.

## Etat actuel (31/07/2026)

Mesure sur un vrai fichier audio (EMMENEZ-MOI-MIMI.wav, rendu MIDI, reference exacte extraite du PDF MVR - voir reference_grid.py), pas sur du synthetique :

- recognize() (lissage a fenetre fixe) : 83.7% exact (113/135), 99.3% fondamentale (134/135), 304 segments detectes
- recognize_viterbi() (lissage HMM/Viterbi) : 85.2% exact (115/135), 99.3% fondamentale (134/135), 349 segments detectes

recognize_viterbi() fait mieux sur la precision mais pas sur la sur-segmentation (plus de segments, pas moins) - un vrai petit gain, pas la percee esperee.

Le chiffre de 96.9% mesure precedemment etait sur audio synthetique - non representatif d'un vrai enregistrement.

### Pistes deja testees et ecartees (resultats negatifs, notes pour ne pas les refaire)

- Detection d'onsets par nouveaute du chroma (pics de changement frame-a-frame) au lieu du lissage a fenetre fixe : a reglages equivalents, aucun gain (83.7% dans le meilleur cas, souvent bien moins avec des seuils plus stricts - perd de vraies frontieres d'accords plutot que juste du bruit).
- Gabarits chroma avec penalites explicites (penaliser un power chord si une tierce est presente, etc.) utilises comme emission pure d'un Viterbi : plafonne a environ 61% exact, moins bon que le classifieur par seuils deja calibre. Le classifieur par ratios d'energie (score_frame dans chord_recognizer.py) reste la meilleure brique de decision par frame trouvee a ce jour ; le seul gain net obtenu vient de le combiner a un lissage Viterbi plutot que de le remplacer.

### Decouverte importante : le tempo affiche par MVR pour ce fichier etait faux

Le PDF de reference indiquait "65 BPM (tempo detecte depuis l'audio)". En calant sur la duree reelle du fichier (236.9s) et le nombre de temps de la grille, le tempo reel est environ 78 BPM. librosa.beat_track seul trouve encore autre chose (97.5 BPM = confusion de niveau metrique). Aucune detection de tempo automatique ne s'en sort ici sans aide - a verifier cote MVR (lie au point "cas valse" deja traite, mais peut-etre pas suffisant).

### Methode

1. Chromagramme CQT (+ correction de justesse).
2. Chroma "basse" separe (registre grave) pour la fondamentale reelle.
3. Decision par ratios d'energie explicites (pas de similarite cosinus par gabarits - ca favorise artificiellement les gabarits a moins de composantes, ex. power chords toujours gagnants). Seuils calibres par recherche en grille contre la reference.
4. Deux options de lissage temporel :
   - recognize() : vote majoritaire glissant a fenetre fixe, puis fusion des micro-segments.
   - recognize_viterbi() : HMM/Viterbi, lissage global sur toute la sequence plutot que local. Emission = le vote du classifieur calibre (etape 3), transition = forte probabilite de rester sur le meme accord.
5. Detection du silence (N.C.) par energie RMS.

### Limite connue - sur-segmentation

Les deux methodes detectent bien plus de segments que les 135 reels (304 et 349). Reduire le lissage capture mieux les accords courts (ex. E vers E7 en milieu de mesure) mais au prix du bruit. Pistes non testees : transitions Viterbi informees par la clef du morceau (probabilites plus hautes vers les accords diatoniques) plutot qu'uniformes ; combiner detection d'onsets et Viterbi plutot que les comparer separement.

### Limite de methodologie d'evaluation

evaluate.py (echantillonnage a des timestamps absolus calcules a partir d'un tempo constant suppose) derive au fil du morceau car les hypotheses de repartition des temps par mesure (2+2 par defaut) ne collent pas exactement a l'audio reel. evaluate_seq.py (alignement de sequence, Needleman-Wunsch) est la mesure fiable a utiliser - elle ne depend d'aucun calage temporel absolu.

## Fichiers

- chord_recognizer.py : le moteur de reconnaissance (recognize() et recognize_viterbi())
- reference_grid.py : reference exacte "Emmenez-moi-mimi" (78 mesures, 135 accords, issue du MIDI via export PDF MVR)
- evaluate_seq.py : evaluation fiable (alignement de sequence), avec option --viterbi
- evaluate.py : evaluation par timestamps absolus (limite : derive, voir plus haut)
- tune.py : recherche en grille des seuils de decision
