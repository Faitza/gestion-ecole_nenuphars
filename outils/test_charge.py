#!/usr/bin/env python3
# outils/test_charge.py : plusieurs visiteurs en même temps sur le site.
#
# Chaque « visiteur » ouvre les pages du site public, puis (s'il a un compte) se connecte
# et parcourt la gestion, en boucle. À la fin : nombre de pages, erreurs, temps de réponse.
# Rien à installer : seulement Python.
#
#   python outils/test_charge.py http://127.0.0.1:8000 --visiteurs 30 --duree 60 \
#          --compte secretaire:secretaire123 --compte prof:prof123
#
# À lancer sur une copie du site (jamais sur le site des familles pendant les cours).
# La limite de requêtes par visiteur répond 429 quand tout vient de la même adresse :
# pour mesurer la vitesse, lancez le serveur d'essai avec DJANGO_LIMITE_PAGES_PAR_MINUTE=100000.
import argparse
import http.cookiejar
import re
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

PAGES_PUBLIQUES = ["/", "/ecole/", "/niveaux/", "/admissions/", "/activites/", "/contact/", "/sante/"]
PAGES_GESTION = ["/gestion/", "/gestion/eleves/", "/gestion/classes/", "/gestion/paiements/", "/gestion/notes/",
                 "/gestion/vie-scolaire/", "/gestion/bulletins/", "/espace/"]


class Resultats:
    def __init__(self):
        self.verrou = threading.Lock()
        self.temps = []
        self.codes = {}
        self.erreurs = []

    def noter(self, chemin, code, secondes):
        with self.verrou:
            self.temps.append(secondes)
            self.codes[code] = self.codes.get(code, 0) + 1
            if code >= 500 or code == 0:
                self.erreurs.append(f"{code} {chemin}")


def ouvrir(navigateur, url, resultats, donnees=None):
    debut = time.perf_counter()
    try:
        with navigateur.open(url, data=donnees, timeout=30) as reponse:
            corps, code, finale = reponse.read(), reponse.status, reponse.geturl()
    except urllib.error.HTTPError as erreur:
        corps, code, finale = erreur.read(), erreur.code, url
    except (urllib.error.URLError, TimeoutError, ConnectionError) as erreur:
        corps, code, finale = str(erreur).encode(), 0, url
    resultats.noter(urllib.parse.urlparse(url).path, code, time.perf_counter() - debut)
    return code, corps, finale


def se_connecter(navigateur, base, compte, resultats):
    identifiant, mot_de_passe = compte.split(":", 1)
    _, page, _ = ouvrir(navigateur, base + "/connexion/", resultats)
    jeton = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', page)
    if not jeton:
        return False
    donnees = urllib.parse.urlencode({"csrfmiddlewaretoken": jeton.group(1).decode(), "username": identifiant,
                                      "password": mot_de_passe}).encode()
    code, _, finale = ouvrir(navigateur, base + "/connexion/", resultats, donnees)
    # Connexion réussie : on est envoyé ailleurs que sur la page de connexion
    return code == 200 and "/connexion/" not in finale


def visiteur(numero, base, comptes, fin, resultats):
    cookies = http.cookiejar.CookieJar()
    navigateur = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    navigateur.addheaders = [("User-Agent", f"test-charge/{numero}"), ("Referer", base + "/connexion/")]
    compte = comptes[numero % len(comptes)] if comptes and numero % 2 == 0 else None
    connecte = se_connecter(navigateur, base, compte, resultats) if compte else False
    if compte and not connecte:
        print(f"Visiteur {numero} : connexion refusée pour {compte.split(':')[0]}")
    pages = PAGES_PUBLIQUES + (PAGES_GESTION if connecte else [])
    i = numero
    while time.time() < fin:
        ouvrir(navigateur, base + pages[i % len(pages)], resultats)
        i += 1


def main():
    parser = argparse.ArgumentParser(description="Plusieurs visiteurs en même temps sur le site.")
    parser.add_argument("adresse", help="ex. http://127.0.0.1:8000")
    parser.add_argument("--visiteurs", type=int, default=20)
    parser.add_argument("--duree", type=int, default=30, help="secondes")
    parser.add_argument("--compte", action="append", default=[], help="identifiant:motdepasse (plusieurs possibles)")
    args = parser.parse_args()
    base = args.adresse.rstrip("/")
    resultats = Resultats()
    fin = time.time() + args.duree
    fils = [threading.Thread(target=visiteur, args=(n, base, args.compte, fin, resultats)) for n in range(args.visiteurs)]
    debut = time.time()
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    duree = time.time() - debut
    temps = sorted(resultats.temps)
    if not temps:
        print("Aucune page n'a répondu.")
        return 1
    p95 = temps[int(len(temps) * 0.95) - 1] if len(temps) > 1 else temps[0]
    print(f"{args.visiteurs} visiteurs pendant {duree:.0f} s : {len(temps)} pages ({len(temps) / duree:.1f} par seconde)")
    print(f"Temps de réponse : médiane {statistics.median(temps) * 1000:.0f} ms, "
          f"95 % en moins de {p95 * 1000:.0f} ms, le plus long {temps[-1] * 1000:.0f} ms")
    print("Réponses : " + ", ".join(f"{code} × {n}" for code, n in sorted(resultats.codes.items())))
    if resultats.erreurs:
        print(f"ERREURS ({len(resultats.erreurs)}) : " + ", ".join(resultats.erreurs[:10]))
        return 1
    print("Aucune erreur.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
