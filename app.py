import requests
from bs4 import BeautifulSoup
import json
import time
import re
from flask import Flask
from threading import Thread

# === KONFIGURASI ===
BASE_LK21 = "https://tv4.lk21official.cc/latest/"
FIREBASE_URL = "https://dutamovies-9bc4c-default-rtdb.asia-southeast1.firebasedatabase.app/movies"
TMDB_API_KEY = "c2360ca3e5a88b7befc29cc20336cbc7"
GITHUB_TOKEN = "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"
REPO_OWNER = "irwa1715"
REPO_NAME = "turbo-m3u8"
WORKFLOW_FILENAME = "run.yml"
LIMIT = 10
DELAY = 30

headers = {"User-Agent": "Mozilla/5.0"}


# === SLUGIFY ===
def slugify(text):
    tahun_match = re.search(r"\((\d{4})\)", text)
    tahun = tahun_match.group(1) if tahun_match else ""
    clean = re.sub(r'\(\d{4}\)', '', text)
    clean = re.sub(r'[^\w\s-]', '', clean)
    clean = clean.lower().strip().replace(" ", "-")
    return f"{clean}-{tahun}" if tahun else clean


def clean_title(title):
    return re.sub(r"\(\d{4}\)", "", title).strip()


def get_film_list():
    res = requests.get(BASE_LK21, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    wrapper = soup.find("div", id="grid-wrapper")
    if not wrapper:
        return []

    film_list = []
    count = 0
    for item in wrapper.find_all("div", class_="infscroll-item"):
        if count >= LIMIT:
            break
        a = item.find("a", href=True)
        img = item.find("img", alt=True)
        if not a or not img:
            continue
        raw_title = img["alt"].strip()
        title = clean_title(raw_title)
        link = a["href"]
        slug = slugify(raw_title)
        film_list.append({"title": title, "slug": slug, "url": link})
        count += 1
    return film_list


def get_tmdb_data(title):
    query = requests.utils.quote(title)
    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}"
    res = requests.get(search_url)
    results = res.json().get("results", [])
    if results:
        m = results[0]
        tmdb_id = m.get("id")
        detail_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}"
        detail_res = requests.get(detail_url)
        detail = detail_res.json()
        genres = [g["name"] for g in detail.get("genres", [])]
        countries = [c["name"] for c in detail.get("production_countries", [])]
        release_year = detail.get("release_date", "")[:4]
        return {
            "overview":
            detail.get("overview", ""),
            "poster":
            "https://image.tmdb.org/t/p/w500" +
            str(detail.get("poster_path", "")),
            "rating":
            detail.get("vote_average", 0),
            "release":
            release_year,
            "tmdb_id":
            tmdb_id,
            "genres":
            genres,
            "countries":
            countries
        }
    return {}


def get_trailer(tmdb_id):
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/videos?api_key={TMDB_API_KEY}"
    res = requests.get(url)
    results = res.json().get("results", [])
    for v in results:
        if v.get("site") == "YouTube" and v.get("type") == "Trailer":
            return v.get("key")
    return ""


def get_turbov_link(film_url):
    try:
        res = requests.get(film_url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        for a in soup.find_all("a", href=True):
            if "turbov" in a["href"]:
                return a["href"]
    except Exception as e:
        print("⚠️ Error ambil turbov:", e)
    return ""


def trigger_gas_for_turbov(slug, turbov_url):
    try:
        encoded = requests.utils.quote(turbov_url, safe="")
        full_url = f"https://script.google.com/macros/s/AKfycbyfE-oj6OVzt29HRjILO3VJR2SCF10yuFQEI7Hu-Lm6vpn76iF4hr7R41ZhlAlEucA/exec?slug={slug}&url={encoded}&key=RAHASIA"
        res = requests.get(full_url)
        print(f"🚀 Trigger GAS: {slug} ({res.status_code})")
    except Exception as e:
        print(f"⚠️ Gagal trigger GAS: {e}")


def trigger_github_action(slug):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/workflows/{WORKFLOW_FILENAME}/dispatches"
    headers_git = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {"ref": "main", "inputs": {"slug": slug}}
    res = requests.post(url, headers=headers_git, json=data)
    if res.status_code == 204:
        print(f"🚀 GitHub workflow triggered for: {slug}")
    else:
        print(f"❌ Failed to trigger GitHub: {res.status_code} {res.text}")


def save_to_firebase(slug, data):
    url = f"{FIREBASE_URL}/{slug}.json"
    res = requests.put(url, data=json.dumps(data))
    print(f"✅ Simpan {slug} ke Firebase ({res.status_code})")


def main():
    film_list = get_film_list()
    print(f"📥 {len(film_list)} film ditemukan.\n")
    for film in film_list:
        print(f"🎬 Proses: {film['title']}")
        slug = film["slug"]
        title_clean = clean_title(film["title"])

        tmdb = get_tmdb_data(title_clean)
        if not tmdb:
            print("⚠️ TMDb tidak ditemukan, lanjut pakai data minimal.")
            tmdb = {
                "overview": "",
                "poster": "",
                "rating": 0,
                "release": "",
                "tmdb_id": None,
                "genres": [],
                "countries": []
            }

        trailer = get_trailer(tmdb["tmdb_id"]) if tmdb["tmdb_id"] else ""
        turbov = get_turbov_link(film["url"])

        if not turbov:
            print("❌ Link player tidak ditemukan.\n")
            continue

        trigger_gas_for_turbov(slug, turbov)

        data = {
            "title": film["title"],
            "overview": tmdb["overview"],
            "poster": tmdb["poster"],
            "rating": tmdb["rating"],
            "release": tmdb["release"],
            "genres": tmdb.get("genres", []),
            "countries": tmdb.get("countries", []),
            "trailer": trailer,
            "player": turbov,
            "m3u8": "",
            "iframe":
            f"https://irwa1715.github.io/m3u8-player/player.html#{slug}"
        }

        save_to_firebase(slug, data)
        trigger_github_action(slug)
        print("⏳ Delay...\n")
        time.sleep(DELAY)


# === FLASK SERVER ===
app = Flask(__name__)


@app.route('/')
def home():
    return "✅ Bot jalan. Tambahkan /run untuk memulai."


@app.route('/run')
def run_bot():
    Thread(target=main).start()
    return "🚀 Bot sedang dijalankan di background."

@app.route('/ping')
def ping():
    return "✅ Ping diterima. Bot masih hidup."



def start_server():
    app.run(host='0.0.0.0', port=8080)


# === ENTRY POINT ===
if __name__ == "__main__":
    Thread(target=start_server).start()
