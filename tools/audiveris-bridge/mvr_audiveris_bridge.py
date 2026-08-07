#!/usr/bin/env python3
"""
Pont local MVR <-> Audiveris.

Expose une petite API HTTP sur 127.0.0.1 (jamais accessible depuis
l'exterieur du PC) que la page web MVR appelle pour transcrire un PDF
de partition via Audiveris, sans que le musicien ait besoin d'ouvrir
Audiveris lui-meme ni de repasser par un editeur externe.

Fonctionnement :
  GET  /ping        -> verifie que le pont tourne et qu'Audiveris est trouve
  POST /transcribe   -> corps = octets bruts du PDF, en-tete X-Filename=nom.pdf
                         reponse = octets bruts du .mxl produit par Audiveris

Demarrage : double-clique sur demarrer_pont.bat (ou "python3 mvr_audiveris_bridge.py")
Arret     : ferme la fenetre, ou Ctrl+C.

Notes navigateur :
  Depuis 2026, Chrome (et les navigateurs bases dessus) demandent une
  autorisation explicite avant qu'une page web (meme MVR) puisse contacter
  un service sur 127.0.0.1 ("Local Network Access"). C'est normal et
  attendu : accepte la demande d'autorisation quand Chrome l'affiche, une
  seule fois par navigateur.
"""
import http.server
import socketserver
import subprocess
import tempfile
import os
import sys
import json
import glob
import shutil
import threading
import time
import re
import io
import zipfile
import xml.etree.ElementTree as ET

# Ces trois bibliotheques ne sont necessaires que pour la fonctionnalite
# "couplets supplementaires via OCR" (voir plus bas) -- si elles ne sont
# pas installees, cette fonctionnalite est simplement desactivee sans
# empecher le reste du pont (transcription Audiveris normale) de marcher.
try:
    import fitz  # PyMuPDF -- rendu des pages PDF en image, sans dependance externe
    import pytesseract
    import pyphen
    OCR_LIBS_OK = True
except ImportError:
    OCR_LIBS_OK = False

PORT = 8791

# Chemins courants d'installation d'Audiveris sur Windows -- le script
# essaie chacun dans l'ordre et garde le premier qui existe.
CANDIDATE_PATHS = [
    r"C:\Program Files\Audiveris\Audiveris.exe",
    r"C:\Program Files\Audiveris\bin\Audiveris.bat",
    r"C:\Program Files (x86)\Audiveris\Audiveris.exe",
    r"C:\Program Files (x86)\Audiveris\bin\Audiveris.bat",
    os.path.expanduser(r"~\AppData\Local\Audiveris\Audiveris.exe"),
    os.path.expanduser(r"~\AppData\Local\Audiveris\bin\Audiveris.bat"),
]


def find_audiveris():
    for p in CANDIDATE_PATHS:
        if os.path.exists(p):
            return p
    return None


AUDIVERIS_PATH = find_audiveris()

# Chemins courants d'installation de Tesseract OCR sur Windows -- utilise
# uniquement pour la reconnaissance des couplets supplementaires (texte
# seul, sans musique) sur une page suivante. Facultatif : si absent, cette
# fonctionnalite est juste desactivee, le reste du pont marche normalement.
TESSERACT_CANDIDATE_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe"),
]


def find_tesseract():
    for p in TESSERACT_CANDIDATE_PATHS:
        if os.path.exists(p):
            return p
    return None


TESSERACT_PATH = find_tesseract()
if OCR_LIBS_OK and TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
VERSES_FEATURE_OK = OCR_LIBS_OK and TESSERACT_PATH is not None


def _run_audiveris(pdf_path, workdir, sheets=None):
    """Lance une commande Audiveris. Si sheets est fourni (ex: "1"), limite
    le traitement a ces pages via l'option -sheets, pour ignorer les pages
    qui ne contiennent pas de musique (voir run_transcription)."""
    cmd = [
        AUDIVERIS_PATH,
        "-batch",
        "-export",
        # Empeche Audiveris de reutiliser un resultat mis en cache d'une
        # tentative precedente sur ce meme fichier (meme nom/contenu) --
        # sans ca, une premiere tentative ratee (ex: reglage de langue
        # invalide, page sans musique) peut laisser un etat fige que les
        # tentatives suivantes reutilisent telles quelles, meme apres
        # correction du reglage en cause.
        "-force",
        "-constant", "org.audiveris.omr.sheet.ProcessingSwitches.chordNames=true",
        "-constant", "org.audiveris.omr.sheet.ProcessingSwitches.lyrics=true",
        # NB : reglage volontairement reduit au strict minimum confirme
        # fonctionnel (le tout premier test reussi utilisait exactement ce
        # reglage a 2 langues). Des essais avec plus de langues combinees
        # (4, puis 12) ont fait echouer completement la reconnaissance de
        # texte d'Audiveris (titre + paroles disparus, "Untitled Score") --
        # Audiveris semble tres sensible au nombre de langues combinees
        # ici, contrairement a Tesseract utilise seul (voir plus bas pour
        # l'OCR des couplets, qui lui tolere une liste bien plus large).
        # Ne pas elargir cette ligne sans un test complet, page reelle,
        # avant de la considerer fiable.
        "-constant", "org.audiveris.omr.text.Language.defaultSpecification=fra+eng",
        "-output", workdir,
    ]
    if sheets:
        cmd += ["-sheets", sheets]
    cmd += ["--", pdf_path]
    return subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=600)


_WORD_RE = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿ\u0370-\u03FF\u0400-\u04FF]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿ]+)?",
    re.UNICODE,
)
_VERSE_NUM_RE = re.compile(r"(?m)^\s*(\d{1,2})[.\s]*$")

# Langues prises en charge pour l'OCR des couplets et leur cesure. Pense a
# a la fois : la reconnaissance Tesseract (le pack de langue doit avoir ete
# installe avec Tesseract, voir demarrer_pont.bat / doc du pont) et la
# disponibilite d'un dictionnaire de cesure dans pyphen. Facilement
# extensible : ajoute une entree ici plutot que de tout re-ecrire.
#   cle = code utilise en interne, valeur = (code langue Tesseract, code langue pyphen)
# Le latin n'a pas de dictionnaire de cesure dedie dans pyphen -- l'italien
# donne une approximation correcte (langues romanes proches en syllabation).
_SUPPORTED_LANGS = {
    "fr": ("fra", "fr"),
    "la": ("lat", "it"),
    "es": ("spa", "es"),
    "en": ("eng", "en"),
    "de": ("deu", "de"),
    "it": ("ita", "it"),
    "pt": ("por", "pt"),
    "nl": ("nld", "nl"),
    "pl": ("pol", "pl"),
    "ro": ("ron", "ro"),
    "ru": ("rus", "ru"),
    "el": ("ell", "el"),
}
_TESSERACT_LANG_STRING = "+".join(v[0] for v in _SUPPORTED_LANGS.values())

try:
    _HYPHEN_DICS = {
        code: pyphen.Pyphen(lang=pyphen_code)
        for code, (_, pyphen_code) in _SUPPORTED_LANGS.items()
    } if OCR_LIBS_OK else {}
except Exception:
    _HYPHEN_DICS = {}

# Petits lots de mots tres frequents par langue, pour deviner la langue
# d'un couplet a partir de son texte OCRise (pas de detection de langue
# fiable a 100%, mais suffisant pour choisir la bonne cesure dans la
# grande majorite des cas -- un cantique reste souvent dans une seule
# langue d'un bout a l'autre).
_LANG_HINT_WORDS = {
    "fr": {"le", "la", "les", "de", "des", "et", "que", "qui", "je", "tu", "il",
           "elle", "nous", "vous", "ils", "est", "pour", "dans", "mon", "ma",
           "ton", "ta", "son", "sa", "ce", "ces", "un", "une", "du", "au",
           "aux", "ne", "pas", "plus", "tout", "tous", "avec", "sur", "notre"},
    "la": {"et", "in", "cum", "ad", "est", "sunt", "deo", "domine", "dominus",
           "filii", "pater", "sancta", "sanctus", "gloria", "christe",
           "christi", "kyrie", "tibi", "nobis", "nostrum", "noster", "qui",
           "te", "deum", "laudamus", "eleison"},
    "es": {"el", "la", "los", "las", "de", "y", "que", "es", "en", "un", "una",
           "por", "para", "con", "tu", "su", "nos", "mi", "este", "esta",
           "pero", "mas", "no", "senor", "dios"},
    "en": {"the", "and", "of", "to", "in", "is", "for", "you", "your", "we",
           "our", "this", "that", "with", "not", "but", "are", "god", "lord"},
    "de": {"der", "die", "das", "und", "ist", "nicht", "ein", "eine", "ich",
           "du", "er", "sie", "wir", "ihr", "mit", "von", "zu", "auf", "im",
           "in", "fur", "gott", "herr", "dein", "mein"},
    "it": {"il", "lo", "la", "le", "gli", "di", "che", "non", "un", "una",
           "io", "tu", "noi", "voi", "con", "per", "dio", "signore", "e",
           "sono", "sei"},
    "pt": {"o", "a", "os", "as", "de", "que", "nao", "um", "uma", "eu", "tu",
           "nos", "com", "para", "deus", "senhor", "e", "sao", "teu"},
    "nl": {"de", "het", "een", "en", "niet", "ik", "jij", "wij", "met",
           "voor", "van", "god", "heer", "uw"},
    "pl": {"i", "w", "na", "nie", "jest", "to", "z", "do", "dla", "bog",
           "pan", "twoj", "nasz"},
    "ro": {"si", "in", "nu", "este", "un", "o", "cu", "pentru", "dumnezeu",
           "domnul", "tau", "noi"},
    "ru": {"и", "в", "не", "на", "я", "ты", "мы", "с", "для", "бог",
           "господь", "твой", "наш"},
    "el": {"και", "το", "η", "ο", "σε", "με", "για", "θεός", "κύριε",
           "εμείς", "εσείς"},
}


def _guess_verse_language(text):
    words = set(w.lower() for w in _WORD_RE.findall(text))
    if not words:
        return "fr"
    scores = {lang: len(words & hints) for lang, hints in _LANG_HINT_WORDS.items()}
    best_lang = max(scores, key=scores.get)
    return best_lang if scores[best_lang] > 0 else "fr"


def _ocr_page_text(page, dpi=300):
    """Rend une page PDF (objet fitz) en image puis en extrait le texte via
    Tesseract. Gere le cas frequent d'une mise en page a 2 colonnes (ex:
    couplets 4 et 5 imprimes cote a cote) en detectant les mots trop
    espaces horizontalement et en relisant chaque moitie separement, sinon
    l'OCR lit les deux colonnes entrelacees ligne par ligne -- illisible."""
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img_bytes = pix.tobytes("png")
    from PIL import Image
    img = Image.open(io.BytesIO(img_bytes))

    data = pytesseract.image_to_data(img, lang=_TESSERACT_LANG_STRING, output_type=pytesseract.Output.DICT)
    xs = [data["left"][i] + data["width"][i] / 2 for i in range(len(data["text"])) if data["text"][i].strip()]
    width = img.width

    is_two_columns = False
    if len(xs) > 6:
        left_half = [x for x in xs if x < width / 2]
        right_half = [x for x in xs if x >= width / 2]
        # Deux colonnes plausibles si les mots se repartissent des deux
        # cotes de maniere significative (pas juste quelques debordements).
        if len(left_half) > len(xs) * 0.25 and len(right_half) > len(xs) * 0.25:
            is_two_columns = True

    if not is_two_columns:
        return pytesseract.image_to_string(img, lang=_TESSERACT_LANG_STRING)

    left_crop = img.crop((0, 0, width // 2, img.height))
    right_crop = img.crop((width // 2, 0, width, img.height))
    return (
        pytesseract.image_to_string(left_crop, lang=_TESSERACT_LANG_STRING)
        + "\n"
        + pytesseract.image_to_string(right_crop, lang=_TESSERACT_LANG_STRING)
    )


def _ocr_extra_verses(pdf_path, skip_page_index=0):
    """OCRise toutes les pages du PDF sauf skip_page_index (0-indexe, en
    general la page 1 qui contient la vraie partition), et en extrait les
    couplets numerotes (ex: "4.", "5."). Retourne un dict {numero: texte}.
    Ne leve jamais d'exception -- retourne {} en cas d'echec ou si les
    bibliotheques necessaires ne sont pas installees."""
    if not VERSES_FEATURE_OK:
        return {}
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for i in range(len(doc)):
            if i == skip_page_index:
                continue
            full_text += "\n" + _ocr_page_text(doc[i])
        doc.close()
    except Exception as e:
        print(f"[pont MVR] OCR des couplets impossible : {e}")
        return {}

    matches = list(_VERSE_NUM_RE.finditer(full_text))
    verses = {}
    for idx, m in enumerate(matches):
        num = int(m.group(1))
        if num < 2 or num > 20:
            continue  # evite de confondre un numero de page ou autre avec un couplet
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        text = full_text[start:end].strip().replace("\n", " ")
        text = re.sub(r"\s+", " ", text)
        if text:
            verses[num] = text

    print("[pont MVR] --- Texte brut OCR (diagnostic) ---")
    for num in sorted(verses):
        print(f"[pont MVR]   Couplet {num} : {verses[num]}")
    print("[pont MVR] --- fin texte brut ---")

    return verses


def _hyphenate_verse(text):
    """Decoupe un texte de couplet en syllabes dans l'ordre, chaque syllabe
    portant son marqueur MusicXML (begin/middle/end/single), via cesure
    automatique dans la langue devinee du couplet (francais/latin/espagnol/
    anglais). Approximation : la cesure automatique ne colle pas toujours
    exactement a la cesure poetique d'origine, mais reste lisible dans
    l'immense majorite des cas."""
    if not _HYPHEN_DICS:
        return []
    lang = _guess_verse_language(text)
    dic = _HYPHEN_DICS.get(lang) or _HYPHEN_DICS.get("fr")
    if not dic:
        return []
    words = _WORD_RE.findall(text)
    syllables = []
    for w in words:
        parts = dic.inserted(w).split("-")
        if len(parts) == 1:
            syllables.append((parts[0], "single"))
        else:
            for i, p in enumerate(parts):
                if i == 0:
                    syllables.append((p, "begin"))
                elif i == len(parts) - 1:
                    syllables.append((p, "end"))
                else:
                    syllables.append((p, "middle"))
    return syllables


def _inject_extra_verses(mxl_bytes, verses):
    """Ajoute les couplets supplementaires (dict {numero: texte}) dans le
    fichier .mxl (zip contenant le MusicXML), en reutilisant les memes
    emplacements de notes que le couplet 1, dans l'ordre. Retourne les
    octets .mxl modifies, ou les octets d'origine inchanges si quoi que ce
    soit echoue -- cette fonctionnalite ne doit jamais faire echouer une
    transcription qui a par ailleurs reussi."""
    if not verses:
        return mxl_bytes
    try:
        zin = zipfile.ZipFile(io.BytesIO(mxl_bytes))
        container = zin.read("META-INF/container.xml").decode("utf-8")
        m = re.search(r'full-path="([^"]+)"', container)
        if not m:
            return mxl_bytes
        xml_path = m.group(1)
        xml_bytes = zin.read(xml_path)

        root = ET.fromstring(xml_bytes)
        slot_notes = []
        for note in root.iter("note"):
            for lyric in note.findall("lyric"):
                if lyric.get("number") == "1":
                    slot_notes.append(note)
                    break

        if not slot_notes:
            print("[pont MVR] Pas de paroles (couplet 1) reconnues sur la partition -- couplets OCR non alignes.")
            return mxl_bytes

        # Diagnostic : le couplet 1 tel qu'Audiveris l'a lui-meme reconnu,
        # dans l'ordre des emplacements de notes -- c'est le "gabarit" sur
        # lequel les couplets OCRises sont ensuite calques.
        verse1_syllables = []
        for note in slot_notes:
            for lyric in note.findall("lyric"):
                if lyric.get("number") == "1":
                    txt_el = lyric.find("text")
                    verse1_syllables.append(txt_el.text if txt_el is not None else "")
                    break
        print(f"[pont MVR] --- Alignement des couplets (diagnostic) ---")
        print(f"[pont MVR]   Emplacements (couplet 1, {len(slot_notes)} notes) : " + "|".join(verse1_syllables))

        for verse_number, verse_text in verses.items():
            syllables = _hyphenate_verse(verse_text)
            lang = _guess_verse_language(verse_text)
            print(f"[pont MVR]   Couplet {verse_number} (langue devinee: {lang}, {len(syllables)} syllabes) : "
                  + "|".join(s[0] for s in syllables))
            if len(syllables) != len(slot_notes):
                print(f"[pont MVR]   /!\\ {len(slot_notes)} emplacements mais {len(syllables)} syllabes "
                      f"pour le couplet {verse_number} -- decalage a partir de la 1ere difference.")
            for note, (syl_text, syl_type) in zip(slot_notes, syllables):
                lyric_el = ET.SubElement(note, "lyric")
                lyric_el.set("number", str(verse_number))
                syllabic_el = ET.SubElement(lyric_el, "syllabic")
                syllabic_el.text = syl_type
                text_el = ET.SubElement(lyric_el, "text")
                text_el.text = syl_text
        print("[pont MVR] --- fin diagnostic alignement ---")

        new_xml_bytes = ET.tostring(root, encoding="UTF-8", xml_declaration=True)

        out_buf = io.BytesIO()
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.namelist():
                if item == xml_path:
                    zout.writestr(item, new_xml_bytes)
                else:
                    zout.writestr(item, zin.read(item))
        print(f"[pont MVR] {len(verses)} couplet(s) supplementaire(s) ajoute(s) via OCR.")
        return out_buf.getvalue()
    except Exception as e:
        print(f"[pont MVR] Ajout des couplets supplementaires impossible ({e}) -- partition conservee telle quelle.")
        return mxl_bytes


_VALID_NOTE_TYPES = {
    "1024th", "512th", "256th", "128th", "64th", "32nd", "16th",
    "eighth", "quarter", "half", "whole", "breve", "long", "maxima",
}


def _sanitize_mxl(mxl_bytes):
    """Corrige les valeurs manifestement invalides qu'Audiveris peut
    produire sur des partitions difficiles pour son OMR (ex: notation
    rythmique en croix/rythme frappe, comme une intro instrumentale avant
    l'entree du chant) -- notamment des balises <duration> ou <type> dont
    le contenu n'est pas un nombre/une valeur MusicXML valide (vu en
    pratique : une seule lettre, ex. "u", visiblement un residu de
    reconnaissance de texte qui a atterri au mauvais endroit). Sans ca,
    OSMD (l'affichage de la partition dans MVR) plante completement --
    ecran blanc avec l'erreur technique "The provided duration is not
    valid" -- au lieu d'afficher la partition, quitte a etre fausse a cet
    endroit precis. Purement defensif : retourne les octets d'origine
    inchanges si quoi que ce soit echoue."""
    try:
        zin = zipfile.ZipFile(io.BytesIO(mxl_bytes))
        container = zin.read("META-INF/container.xml").decode("utf-8")
        m = re.search(r'full-path="([^"]+)"', container)
        if not m:
            return mxl_bytes
        xml_path = m.group(1)
        xml_text = zin.read(xml_path).decode("utf-8")

        _fix_count = [0]

        def _fix_duration(mo):
            if mo.group(2).strip().isdigit():
                return mo.group(0)
            _fix_count[0] += 1
            return mo.group(1) + "4" + mo.group(3)

        def _fix_type(mo):
            if mo.group(2).strip() in _VALID_NOTE_TYPES:
                return mo.group(0)
            _fix_count[0] += 1
            return mo.group(1) + "quarter" + mo.group(3)

        fixed_text = re.sub(r"(<duration>)([^<]*)(</duration>)", _fix_duration, xml_text)
        fixed_text = re.sub(r"(<type[^>]*>)([^<]*)(</type>)", _fix_type, fixed_text)

        # Caracteres parasites frequents dans les noms d'accords mal lus par
        # Audiveris (ex: "|", "¦", "!") -- n'apparaissent jamais dans un vrai
        # nom d'accord (do/re/mi... + m/maj/dim/sus...). On ne peut pas
        # deviner le bon accord a la place, mais on evite au moins d'
        # afficher un symbole illisible du genre "|V|l m".
        _chord_noise_re = re.compile(r"[|¦!]+")

        def _clean_chord_noise(mo):
            cleaned = _chord_noise_re.sub("", mo.group(2))
            if cleaned != mo.group(2):
                _fix_count[0] += 1
            return mo.group(1) + cleaned + mo.group(3)

        fixed_text = re.sub(r"(<root-step>)([^<]*)(</root-step>)", _clean_chord_noise, fixed_text)
        fixed_text = re.sub(r"(<bass-step>)([^<]*)(</bass-step>)", _clean_chord_noise, fixed_text)

        def _clean_kind_tag(mo):
            cleaned = _chord_noise_re.sub("", mo.group(2))
            if cleaned != mo.group(2):
                _fix_count[0] += 1
            return mo.group(1) + cleaned + '"'

        fixed_text = re.sub(r'(<kind[^>]*\btext=")([^"]*)"', _clean_kind_tag, fixed_text)

        # Diagnostic pour les prochains cas non couverts par les deux regles
        # ci-dessus : toute balise dont le contenu est un seul caractere non
        # numerique (le residu type "u" observe en pratique peut atterrir
        # dans a peu pres n'importe quel champ). On corrige au passage en
        # supprimant juste ce caractere isole, plutot que de laisser OSMD
        # planter dessus -- et on log precisement ou, pour un vrai
        # diagnostic si ca se reproduit encore.
        for _tag_mo in re.finditer(r"<(\w[\w-]*)>([a-zA-Z])</\1>", fixed_text):
            print(f"[pont MVR] /!\\ Contenu suspect (1 caractere) dans <{_tag_mo.group(1)}> : "
                  f"\"{_tag_mo.group(2)}\" -- probablement un residu de reconnaissance de texte.")

        n = _fix_count[0]
        if n == 0:
            return mxl_bytes

        out_buf = io.BytesIO()
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.namelist():
                if item == xml_path:
                    zout.writestr(item, fixed_text.encode("utf-8"))
                else:
                    zout.writestr(item, zin.read(item))
        print(f"[pont MVR] {n} valeur(s) de duree invalide(s) corrigee(s) dans la partition.")
        return out_buf.getvalue()
    except Exception as e:
        print(f"[pont MVR] Nettoyage des durees impossible ({e}) -- partition envoyee telle quelle.")
        return mxl_bytes


def run_transcription(pdf_bytes, original_name):
    """Ecrit le PDF dans un dossier temporaire, lance Audiveris en mode
    batch avec les reglages qu'on utilise habituellement a la main
    (langue fra+eng, paroles, accords), puis retourne les octets du .mxl
    produit. Leve une exception avec un message clair en cas d'echec."""
    if not AUDIVERIS_PATH:
        raise RuntimeError(
            "Audiveris introuvable. Chemins verifies : "
            + ", ".join(CANDIDATE_PATHS)
            + " -- modifie CANDIDATE_PATHS en haut du script si besoin."
        )

    workdir = tempfile.mkdtemp(prefix="mvr_audiveris_")
    safe_name = "".join(c for c in original_name if c not in '<>:"/\\|?*') or "partition.pdf"
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"
    pdf_path = os.path.join(workdir, safe_name)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    result = _run_audiveris(pdf_path, workdir)
    mxl_files = glob.glob(os.path.join(workdir, "**", "*.mxl"), recursive=True)

    used_page1_fallback = False
    if not mxl_files:
        # Cas frequent avec les vieux recueils de cantiques/psaumes : la
        # musique tient sur la 1ere page, et les couplets suivants (4, 5...)
        # sont imprimes en texte seul sur une page suivante, sans aucune
        # portee. Audiveris essaie d'y reconnaitre de la musique quand meme,
        # echoue dessus, et ca fait echouer l'export du livre entier -- meme
        # si la vraie partition (page 1) a ete correctement transcrite.
        # On retente alors en ne traitant que la premiere page.
        print("[pont MVR] Echec sur toutes les pages, nouvelle tentative en limitant a la page 1...")
        result = _run_audiveris(pdf_path, workdir, sheets="1")
        mxl_files = glob.glob(os.path.join(workdir, "**", "*.mxl"), recursive=True)
        used_page1_fallback = mxl_files != []

    if not mxl_files:
        tail = (result.stdout or "")[-1500:] + "\n" + (result.stderr or "")[-1500:]
        raise RuntimeError(
            "Audiveris n'a produit aucun fichier .mxl (meme en limitant a la "
            "1ere page). Sortie du programme (fin) :\n" + tail
        )

    with open(mxl_files[0], "rb") as f:
        mxl_bytes = f.read()

    if used_page1_fallback and VERSES_FEATURE_OK:
        # La page 1 seule a ete transcrite -- les autres pages contiennent
        # probablement des couplets supplementaires en texte seul (voir
        # commentaire ci-dessus). On tente de les recuperer par OCR et de
        # les ajouter a la partition, alignes sur les memes emplacements de
        # notes que le couplet 1. Purement best-effort : n'importe quel
        # souci ici laisse simplement la partition telle qu'elle etait.
        try:
            extra_verses = _ocr_extra_verses(pdf_path, skip_page_index=0)
            if extra_verses:
                print(f"[pont MVR] Couplet(s) detecte(s) par OCR : {sorted(extra_verses.keys())}")
                mxl_bytes = _inject_extra_verses(mxl_bytes, extra_verses)
        except Exception as e:
            print(f"[pont MVR] OCR des couplets supplementaires ignore ({e}).")

    # Nettoyage best-effort -- ne bloque jamais la reponse si ca echoue
    try:
        shutil.rmtree(workdir, ignore_errors=True)
    except Exception:
        pass

    mxl_bytes = _sanitize_mxl(mxl_bytes)

    return mxl_bytes


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[pont MVR] " + (fmt % args) + "\n")

    def _cors(self):
        # En-tetes necessaires pour qu'une page servie en HTTPS (MVR sur
        # Cloudflare) soit autorisee par le navigateur a contacter ce
        # service local (Local Network Access / ex-Private Network Access).
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-Filename, Access-Control-Request-Private-Network",
        )
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/ping":
            body = json.dumps(
                {
                    "status": "ok",
                    "audiverisFound": AUDIVERIS_PATH is not None,
                    "audiverisPath": AUDIVERIS_PATH,
                    "extraVersesOcrAvailable": VERSES_FEATURE_OK,
                }
            ).encode("utf-8")
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self._cors()
            self.end_headers()

    def _send_error(self, code, message):
        body = json.dumps({"status": "error", "message": message}).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/transcribe":
            self._send_error(404, "Route inconnue.")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                self._send_error(400, "Corps de requete vide.")
                return
            pdf_bytes = self.rfile.read(length)
            original_name = self.headers.get("X-Filename", "partition.pdf")
            print(f"[pont MVR] Transcription de {original_name} ({length} octets)...")
            mxl_bytes = run_transcription(pdf_bytes, original_name)
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(mxl_bytes)))
            self.end_headers()
            self.wfile.write(mxl_bytes)
            print(f"[pont MVR] OK -- {len(mxl_bytes)} octets renvoyes.")
        except subprocess.TimeoutExpired:
            self._send_error(504, "Audiveris a depasse le delai de 10 minutes.")
        except Exception as e:
            print(f"[pont MVR] ERREUR : {e}")
            self._send_error(500, str(e))


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def main():
    print("=" * 60)
    print(" Pont local MVR <-> Audiveris")
    print("=" * 60)
    if AUDIVERIS_PATH:
        print(f"Audiveris trouve : {AUDIVERIS_PATH}")
    else:
        print("!! Audiveris INTROUVABLE dans les emplacements standards.")
        print("   Modifie CANDIDATE_PATHS en haut de ce script si besoin.")
    if VERSES_FEATURE_OK:
        print(f"Couplets supplementaires (OCR) : actif -- Tesseract trouve : {TESSERACT_PATH}")
    elif not OCR_LIBS_OK:
        print("Couplets supplementaires (OCR) : desactive -- bibliotheques Python manquantes.")
        print("   Pour l'activer : pip install pymupdf pytesseract pillow pyphen --break-system-packages")
        print("   (ou 'py -m pip install ...' selon ton installation Python)")
    else:
        print("Couplets supplementaires (OCR) : desactive -- Tesseract OCR introuvable.")
        print("   Installe-le depuis https://github.com/UB-Mannheim/tesseract/wiki")
        print("   (coche la langue French pendant l'installation), ou modifie")
        print("   TESSERACT_CANDIDATE_PATHS en haut de ce script si besoin.")
    print(f"Ecoute sur http://127.0.0.1:{PORT}")
    print("Laisse cette fenetre ouverte pendant que tu utilises MVR.")
    print("Ferme-la (ou Ctrl+C) pour arreter le pont.")
    print("=" * 60)
    with ThreadingServer(("127.0.0.1", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nArret du pont.")


if __name__ == "__main__":
    main()
