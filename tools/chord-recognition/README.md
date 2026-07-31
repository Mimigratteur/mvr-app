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

### Mesures honnetes sur vrai enregistrement (31/07/2026, apres-midi, suite)

Premiere vraie validation chiffree sur audio reel, contre deux references
independantes (grille Chordify pour La Corrida, progression connue et
publiee pour l'intro de Still Got the Blues) :

- **La Corrida** : 47% de fondamentale correcte (7/15) sur le debut du
  morceau
- **Still Got the Blues** : 43% de fondamentale correcte (3/7) sur
  l'intro

Attention methodologique : une premiere comparaison par alignement
global avait donne 67% pour La Corrida - artefact trompeur, l'alignement
avait accroche une repetition tardive du motif plutot que le vrai debut
du morceau (la reference Chordify n'est qu'une boucle courte). Toujours
comparer en bornant sur la meme fenetre temporelle, pas par alignement
libre sur tout le morceau.

Constat important : l'observation precedente ("Am domine, coherent avec
la tonalite du morceau") etait un FAUX bon signe. La vraie intro de
Still Got the Blues est Dm7-G-Cmaj7-Fmaj7-Bm-E7-Am (7 accords distincts,
resolution sur Am seulement a la fin) ; l'outil detecte "Am" presque
partout des le debut - pas un vrai suivi des changements d'accords, plus
probablement un biais vers la tonique/fondamentale la plus resonante.

### Ecart avec Chordify et autres outils commerciaux

Chordify et autres solutions matures annoncent des taux proches de 90%
sur vrai enregistrement. L'ecart avec nos ~45% actuels vient
probablement d'un ou plusieurs facteurs non encore corriges :
- Selection de fondamentale sensible a une note isolee tres resonante
  (corde a vide, note de basse de passage) plutot qu'a la stabilite
  reelle sur la duree de l'accord
- Pas de modele de tonalite/gamme pour departager les cas ambigus
- Fenetre d'agregation fixe (1.5s) plutot qu'alignee sur les vrais
  temps/mesures du morceau
- Decalage de capo eventuel non pris en compte (a verifier : les
  references lues affichent-elles les accords "position" ou "sonnants" ?)

Prochaine piste a tester avant tout resultat chiffre supplementaire :
verifier si un decalage constant de demi-tons ameliore l'alignement
(capo, ou erreur de justesse systematique) avant de re-attaquer
l'algorithme de selection de fondamentale.

**Teste et confirme** : le decalage constant (capo/justesse) N'EST PAS
la cause - aucun decalage de 1 a 11 demi-tons ne bat le decalage 0 sur
les deux morceaux. Les erreurs sont dispersees, pas systematiques.

**Amelioration reelle trouvee et integree** : la selection de
fondamentale par MEDIANE sur la fenetre peut etre trompee par une note
de passage forte mais breve. En prenant le MINIMUM sur la fenetre au
lieu de la mediane (ne retient que ce qui est present en permanence,
pas juste fort a un instant), avec une fenetre elargie a 2.0s :
- La Corrida : 47% -> 53% de fondamentale correcte
- Still Got the Blues : 43% -> 71% de fondamentale correcte

Gain reel mais pas uniforme (net sur un morceau, marginal sur l'autre).
`recognize_windowed()` utilise maintenant ces reglages par defaut
(window_s=2.0, stability='min'). Sweep de bass_bonus/third_thresh
au-dessus de cette config : aucun gain supplementaire trouve (plafond a
59% cumule sur les deux morceaux, soit 13/22).

Encore loin des ~90% d'outils matures comme Chordify. Passer ce cap
demanderait vraisemblablement un changement d'approche plus profond
(modele de tonalite/gamme pour departager les cas ambigus, ou modele
entraine sur de vraies donnees plutot que des seuils fixes) plutot que
du reglage fin supplementaire sur cette methode par ratios d'energie.

### Modele de tonalite (Krumhansl-Kessler) - amelioration validee (31/07/2026, soir)

Piste identifiee ci-dessus mise en oeuvre : estimation de la tonalite du
morceau entier (fondamentale + majeur/mineur) par correlation avec les
profils de Krumhansl-Kessler (standard en MIR), utilisee comme leger a
priori pour departager les accords ambigus (fonction estimate_key +
diatonic_bonus dans chord_recognizer.py).

Detection de tonalite verifiee correcte sur les 3 fichiers connus :
- La Corrida -> Re mineur (coherent avec la grille Chordify : Dm, Bb, Gm, F, C)
- Still Got the Blues -> La mineur (coherent avec la tonalite connue et publiee, tres haute confiance)
- Emmenez-moi-mimi -> La mineur (coherent avec reference_grid.py)

Impact mesure sur les deux vrais enregistrements (meme protocole que
plus haut, comparaison bornee au debut du morceau) :
- Exact (fondamentale + qualite) : 23% -> **45%** (10/22, avant/apres)
- Fondamentale seule : 59% (13/22, inchangee - le gain vient presque
  entierement de la decision maj/min, pas du choix de fondamentale)

`recognize_windowed()` utilise maintenant use_key=True et key_weight=0.6
par defaut (poids choisi au milieu d'un plateau stable 0.4-0.7, pas au
bord d'un pic isole, pour eviter le sur-ajustement sur seulement 2
morceaux de test). Le prior de tonalite est un bonus modeste ajoute au
score par energie, jamais une decision forcee contre une preuve audio
claire.

Important : `recognize()` et `recognize_viterbi()` (audio MIDI) ne sont
PAS affectes par ce changement - ils n'utilisent pas key_root/key_mode,
leurs resultats restent exactement 83.7%/85.2% comme avant.

### Transitions Viterbi informees par la tonalite - amelioration validee (31/07/2026, soir, suite)

Nouvelle fonction recognize_key_viterbi() : combine recognize_windowed()
(fenetres ~2s, agregation par minimum, a priori de tonalite par accord)
avec un lissage Viterbi dont la matrice de TRANSITION est elle-meme
informee par la tonalite - les enchainements vers un accord diatonique
de la cle sont favorises, pas juste "rester sur le meme accord".

Resultat (meme protocole, comparaison bornee au debut de deux vrais
enregistrements) :
- Exact (fondamentale + qualite) : 45% -> **55%** (12/22)
- Fondamentale seule : 59% -> **68%** (15/22)

Plateau stable trouve par recherche en grille (stay_prob 0.4-0.5,
diatonic_bonus_prob 5-20 tous equivalents) - pas un pic isole de
sur-ajustement sur les 2 morceaux de test.

**Progression complete de la session du 31/07/2026 sur vrai
enregistrement** : 0% mesure de facon fiable (avant) -> 23% -> 45% ->
**55% exact**. Reel progres, mais plafond honnete a rappeler : les
outils matures comme Chordify tournent autour de 85-90%, et la
litterature scientifique sur la reconnaissance d'accords automatique
situe meme les meilleurs systemes publies autour de 80-85% en conditions
reelles. Viser 99% n'est pas un objectif realiste avec cette methode par
regles/seuils calibres a la main - ni probablement avec aucune methode
connue a ce jour sur de la musique polyinstrumentale reelle. Aller
significativement au-dela de 55-60% demanderait vraisemblablement un
modele entraine sur de vraies donnees annotees a grande echelle, pas un
reglage supplementaire de cette approche.

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

- chord_recognizer.py : le moteur de reconnaissance (recognize(), recognize_viterbi() pour audio MIDI ; recognize_windowed(), recognize_key_viterbi() pour vrai enregistrement - cette derniere est la meilleure methode actuelle sur vrai enregistrement)
- reference_grid.py : reference exacte "Emmenez-moi-mimi" (78 mesures, 135 accords, issue du MIDI via export PDF MVR)
- evaluate_seq.py : evaluation fiable (alignement de sequence), avec option --viterbi
- evaluate.py : evaluation par timestamps absolus (limite : derive, voir plus haut)
- tune.py : recherche en grille des seuils de decision
