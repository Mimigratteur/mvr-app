# Reconnaissance d'accords — outil autonome (hors MVR)

Outil Python indépendant pour extraire une grille d'accords depuis un
fichier audio. **Volontairement hors de MVR** : MVR est une PWA 100%
navigateur (pas de serveur), et cet outil sert à isoler et résoudre le
problème de reconnaissance avant tout portage éventuel — même logique que
la décision prise pour l'import .gp3/.gp4/.gp5 (Python en outil de
conversion externe, jamais embarqué dans l'app).

## Installation

```bash
pip install librosa numpy scipy soundfile
```

## Utilisation

```bash
# Reconnaissance sur un fichier audio, affiche les segments détectés
python3 chord_recognizer.py mon_morceau.wav

# Évaluer contre la référence "Emmenez-moi-mimi" (voir reference_grid.py)
python3 evaluate_seq.py -v      # alignement de séquence, détail des erreurs
python3 evaluate.py -v          # évaluation par échantillonnage temps-absolu (moins fiable, voir limites)

# Recalibrer les seuils de décision (recherche en grille)
python3 tune.py
```

## État actuel (31/07/2026)

**Mesuré sur un vrai fichier audio** (`EMMENEZ-MOI-MIMI.wav`, rendu MIDI,
référence exacte extraite du PDF MVR — voir `reference_grid.py`), pas sur
du synthétique :

- **Fondamentale correcte : 99,3%** (134/135 accords)
- **Accord exact (fondamentale + qualité) : 83,7%** (113/135 accords)

(Le chiffre de 96,9% mesuré précédemment était sur audio **synthétique**
— non représentatif d'un vrai enregistrement.)

### Découverte importante : le tempo affiché par MVR pour ce fichier était faux

Le PDF de référence indiquait "65 BPM (tempo détecté depuis l'audio)".
En calant sur la durée réelle du fichier (236,9s) et le nombre de temps
de la grille, le tempo réel est ~78 BPM. `librosa.beat_track` seul
trouve encore autre chose (97,5 BPM = confusion de niveau métrique).
**Aucune détection de tempo automatique ne s'en sort ici sans aide** — à
vérifier côté MVR (lié au point "cas valse" déjà traité, mais peut-être
pas suffisant).

### Méthode

1. Chromagramme CQT (+ correction de justesse).
2. Chroma "basse" séparé (registre grave) pour la fondamentale réelle.
3. Décision par **ratios d'énergie explicites** (pas de similarité
   cosinus par gabarits — ça favorise artificiellement les gabarits
