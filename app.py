import html
import json
import os
import re
import socket
import sys
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from flask import Flask, abort, redirect, render_template, request

# The exe unpacks bundled files into sys._MEIPASS, not next to app.py.
app = Flask(__name__, template_folder=os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "templates"))

BASE = "https://letterboxd.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
EMPTY_POSTER = "https://s.ltrbxd.com/static/img/empty-poster-230-AiuBHVCI.png"
SLUG = re.compile(r"[a-z0-9-]+")
FILM = re.compile(r'data-item-name="([^"]*)"[^>]*?data-item-slug="([^"]+)"')
TITLE = re.compile(r'<meta property="og:title" content="([^"]*)"')
pool = ThreadPoolExecutor(8)


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": UA}), timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def normalize(url):
    """Turn any letterboxd list/watchlist URL into its canonical path, or None."""
    u = urlparse(url.strip() if "://" in url else "https://" + url.strip())
    if u.hostname not in ("letterboxd.com", "www.letterboxd.com"):
        return None
    parts = [p for p in u.path.split("/") if p]
    if "page" in parts:
        parts = parts[: parts.index("page")]
    ok = (len(parts) >= 2 and parts[1] in ("watchlist", "films")) or (len(parts) >= 3 and parts[1] == "list")
    return "/" + "/".join(parts) + "/" if ok else None


def parse(page):
    """[(slug, name, year)] in page order."""
    out = []
    for name, slug in FILM.findall(page):
        name = html.unescape(name)
        m = re.match(r"(.*) \((\d{4})\)$", name)
        out.append((slug, *(m.groups() if m else (name, ""))))
    return out


def scrape(path):
    first = fetch(BASE + path)
    pages = [int(n) for n in re.findall(re.escape(path) + r"page/(\d+)/", first)]
    rest = pool.map(lambda n: fetch(f"{BASE}{path}page/{n}/"), range(2, max(pages, default=1) + 1))
    films = [f for p in [first, *rest] for f in parse(p)]
    title = TITLE.search(first)
    return html.unescape(title.group(1)) if title else path, films


@lru_cache(maxsize=4096)
def poster_url(slug):
    try:
        return json.loads(fetch(f"{BASE}/film/{slug}/poster/std/230/"))["url"]
    except Exception:
        return EMPTY_POSTER


@app.get("/poster/<slug>")
def poster(slug):
    if not SLUG.fullmatch(slug):
        abort(404)
    return redirect(poster_url(slug))


@app.route("/", methods=["GET", "POST"])
def index():
    urls = [u for u in request.form.getlist("url") if u.strip()]
    if request.method == "GET" or not urls:
        return render_template("index.html", urls=urls or ["", ""])

    errors, lists = [], []
    for raw in urls:
        path = normalize(raw)
        if not path:
            errors.append(f"“{raw}” isn’t a Letterboxd list, watchlist or films page.")
            continue
        try:
            lists.append(scrape(path))
        except HTTPError as e:
            errors.append(f"Couldn’t open {path} (Letterboxd said {e.code}). Check it’s public and spelled right.")
        except OSError:
            errors.append(f"Couldn’t reach Letterboxd for {path}. Try again in a moment.")

    common = None
    if len(lists) >= 2:
        shared = set.intersection(*({f[0] for f in films} for _, films in lists))
        common = [f for f in dict.fromkeys(lists[0][1]) if f[0] in shared]
    urls += [""] * (2 - len(urls))
    return render_template("index.html", urls=urls, lists=lists, common=common, errors=errors)


@app.post("/quit")
def quit_app():
    threading.Timer(0.5, os._exit, [0]).start()
    return "<body style='background:#1a1420;color:#efe6dc;font:1.1rem system-ui;padding:3rem'>Letterboxd Intersection has stopped. You can close this tab.</body>"


if __name__ == "__main__":
    if getattr(sys, "frozen", False):  # running as the windowless PyInstaller exe
        url = "http://localhost:5000"
        with socket.socket() as s:
            already_running = s.connect_ex(("127.0.0.1", 5000)) == 0
        if not already_running:
            sys.stdout = sys.stderr = open(os.devnull, "w")  # no console to write to
            threading.Timer(1, webbrowser.open, [url]).start()
            app.run(port=5000)
        else:
            webbrowser.open(url)
    else:
        app.run(debug=True)
