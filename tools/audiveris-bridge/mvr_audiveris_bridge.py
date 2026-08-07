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


def _run_audiveris(pdf_path, workdir, sheets=None):
    """Lance une commande Audiveris. Si sheets est fourni (ex: "1"), limite
    le traitement a ces pages via l'option -sheets, pour ignorer les pages
    qui ne contiennent pas de musique (voir run_transcription)."""
    cmd = [
        AUDIVERIS_PATH,
        "-batch",
        "-export",
        "-constant", "org.audiveris.omr.sheet.ProcessingSwitches.chordNames=true",
        "-constant", "org.audiveris.omr.sheet.ProcessingSwitches.lyrics=true",
        "-constant", "org.audiveris.omr.text.Language.defaultSpecification=fra+eng",
        "-output", workdir,
    ]
    if sheets:
        cmd += ["-sheets", sheets]
    cmd += ["--", pdf_path]
    return subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=600)


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

    if not mxl_files:
        tail = (result.stdout or "")[-1500:] + "\n" + (result.stderr or "")[-1500:]
        raise RuntimeError(
            "Audiveris n'a produit aucun fichier .mxl (meme en limitant a la "
            "1ere page). Sortie du programme (fin) :\n" + tail
        )

    with open(mxl_files[0], "rb") as f:
        mxl_bytes = f.read()

    # Nettoyage best-effort -- ne bloque jamais la reponse si ca echoue
    try:
        shutil.rmtree(workdir, ignore_errors=True)
    except Exception:
        pass

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
