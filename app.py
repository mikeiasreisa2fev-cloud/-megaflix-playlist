from flask import Flask, Response, redirect, request
import requests
import re
import os
import json
import base64
import time
import threading
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# --- CONFIGURAÇÕES DE PERFORMANCE MÁXIMA ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=500, max_retries=5)
session.mount('https://', adapter)

UA_OFFICIAL = "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
HEADERS = {
    "User-Agent": UA_OFFICIAL,
    "X-Requested-With": "com.megaflix.app",
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "Connection": "keep-alive"
}
session.headers.update(HEADERS)

db = {"links": {}, "ids": [], "last_playlist": "", "pluto_cache": ""}

# --- LISTA MANUAL [S2] ATUALIZADA (V19.2) ---
MANUAL_CHANNELS = [
    ("RÁTIMBUM [S2]", "http://45.190.28.50/RATIMBUM/index.m3u8"),
    ("NICKONLINE [S2]", "https://x1colegal.com/"),
    ("NICKTOONS [S2]", "https://stmv2.srvif.com/nicktoons/nicktoons/playlist.m3u8"),
    ("GLOBO NEWS [S2]", "http://177.52.24.163/GLOBO-NEWS-HD/index.m3u8"),
    ("GLOBO RJ [S2]", "http://138.255.2.6:8084/GLOBOHD/index.m3u8"),
    ("GLOBO MG [S2]", "http://189.76.71.35:8555/live/cdn_stonetv/cdn_stonetv/1132.m3u8"),
    ("TV SENADO [S2]", "http://138.255.2.6:8084/TVSENADO/index.m3u8"),
    ("SBT SP [S2]", "http://138.255.2.6:8084/SBT/index.m3u8"),
    ("BAND [S2]", "http://138.255.2.6:8084/BAND/index.m3u8"),
    ("BAND NEWS [S2]", "http://138.255.2.6:8084/BANDNEWS/index.m3u8"),
    ("TV CULTURA [S2]", "http://138.255.2.6:8084/CULTURA/index.m3u8"),
    ("RECORD NEWS [S2]", "http://138.255.2.6:8084/RECORDNEWS/index.m3u8"),
    ("CNN BRASIL [S2]", "http://138.255.2.6:8084/CNNBRASIL/index.m3u8"),
    ("CARTOONITO [S2]", "http://45.190.28.50/BOOMERANG_HD/index.m3u8"),
    ("CARTOON NETWORK [S2]", "http://45.190.28.50/CARTOON_HD/index.m3u8"),
    ("DISCOVERY KIDS [S2]", "http://45.190.28.50/DISCOVERY_KIDS_HD/index.m3u8"),
    ("ADULT SWIM [S2]", "http://45.190.28.50/TRUTV_HD/index.m3u8"),
    ("GLOBINHO [S2]", "http://177.52.24.163/GLOOBINHO-HD/index.m3u8"),
    ("PREMIERE 1 [S2]", "http://177.52.24.163/PREMIERE-1-HD/index.m3u8"),
    ("PREMIERE 2 [S2]", "http://177.52.24.163/PREMIERE-2-HD/index.m3u8"),
    ("PREMIERE 3 [S2]", "http://177.52.24.163/PREMIERE-3-HD/index.m3u8"),
    ("PREMIERE 4 [S2]", "http://177.52.24.163/PREMIERE-4-HD/index.m3u8"),
    ("PREMIERE 7 [S2]", "http://177.52.24.163/PREMIERE-7-HD/index.m3u8"),
    ("PREMIERE 8 [S2]", "http://177.52.24.163/PREMIERE-8-HD/index.m3u8"),
    ("SPORT TV 1 [S2]", "http://177.52.24.163/SPORTV-1-HD/index.m3u8"),
    ("SPORT TV 2 [S2]", "http://177.52.24.163/SPORTV-2-HD/index.m3u8"),
    ("SPORT TV 3 [S2]", "http://177.52.24.163/SPORTV-3-HD/index.m3u8"),
    ("ESPN 1 [S2]", "http://177.52.24.163/ESPN-1-HD/index.m3u8"),
    ("ESPN 1 (ALT) [S2]", "http://45.190.28.50/ESPN_HD/index.m3u8"),
    ("ESPN 2 [S2]", "http://177.52.24.163/ESPN-2-HD/index.m3u8"),
    ("ESPN 2 (ALT) [S2]", "http://45.190.28.50/ESPN2_HD/index.m3u8"),
    ("ESPN 3 [S2]", "http://177.52.24.163/ESPN-3-HD/index.m3u8"),
    ("ESPN 3 (ALT) [S2]", "http://45.190.28.50/ESPN3_HD/index.m3u8"),
    ("ESPN 4 [S2]", "http://177.52.24.163/ESPN-4-HD/index.m3u8"),
    ("ESPN 4 (ALT) [S2]", "http://45.190.28.50/ESPN4_HD/index.m3u8"),
    ("ESPN 5 [S2]", "http://177.52.24.163/ESPN-5-HD/index.m3u8"),
    ("ESPN 5 (ALT) [S2]", "http://45.190.28.50/ESPN5/index.m3u8"),
    ("ESPN 6 [S2]", "http://45.190.28.50/ESPN_EXTRA_HD/index.m3u8"),
    ("SPORTYNET 1 [S2]", "http://177.52.24.163/SPORTYNET-1-HD/index.m3u8"),
    ("SPORTYNET 2 [S2]", "http://177.52.24.163/SPORTYNET-2-HD/index.m3u8"),
    ("SPORTYNET 3 [S2]", "http://177.52.24.163/SPORTYNET-3-HD/index.m3u8"),
    ("BAND SPORTS [S2]", "http://45.190.28.50/BAND_SPORTS_HD/index.m3u8"),
    ("GE TV [S2]", "http://177.52.24.163/GETV-HD/index.m3u8"),
    ("CAZE TV [S2]", "http://177.52.24.163/CAZE-TV/index.m3u8"),
    ("HISTORY CHANNEL [S2]", "http://177.52.24.163/HISTORY-HD/index.m3u8"),
    ("DISCOVERY CHANNEL [S2]", "http://177.52.24.163/DISCOVERY-CHANNEL-HD/index.m3u8"),
    ("DISCOVERY (ALT) [S2]", "http://45.190.28.50/DISCOVERY_HD/index.m3u8"),
    ("DISCOVERY SCIENCE [S2]", "http://177.52.24.163/DISCOVERY-SCIENCE-HD/index.m3u8"),
    ("DISC. SCIENCE (ALT) [S2]", "http://45.190.28.50/DISCOVERY_SCIENCE_HD/index.m3u8"),
    ("DISCOVERY TURBO [S2]", "http://177.52.24.163/DISCOVERY-TURBO-HD/index.m3u8"),
    ("DISC. TURBO (ALT) [S2]", "http://45.190.28.50/DISCOVERY_TURBO_HD/index.m3u8"),
    ("DISCOVERY WORLD [S2]", "http://177.52.24.163/DISCOVERY-WORLD-HD/index.m3u8"),
    ("DISC. WORLD (ALT) [S2]", "http://45.190.28.50/DISCOVERY_WORLD_HD/index.m3u8"),
    ("DISC. HOME & HEALT [S2]", "http://177.52.24.163/DISCOVERY-HH-HD/index.m3u8"),
    ("DISCOVERY THEATER [S2]", "http://45.190.28.50/DISCOVERY_THEATER_HD/index.m3u8"),
    ("ID [S2]", "http://45.190.28.50/ID_HD/index.m3u8"),
    ("ANIMAL PLANET [S2]", "http://138.255.2.6:8084/ANIMALPLANET/index.m3u8"),
    ("ANIMAL PLANET (ALT) [S2]", "http://45.190.28.50/ANIMAL_PLANET_HD/index.m3u8"),
    ("HGTV [S2]", "http://45.190.28.50/HGTV_HD/index.m3u8"),
    ("CINEMAX [S2]", "http://45.190.28.50/CINEMAX/index.m3u8"),
    ("LIFETIME [S2]", "http://138.255.2.6:8084/LIFETIME/index.m3u8"),
    ("SPACE [S2]", "http://138.255.2.6:8084/SPACE/index.m3u8"),
    ("MEGAPIX [S2]", "http://177.52.24.163/MEGAPIX-HD/index.m3u8"),
    ("AXN [S2]", "http://138.255.2.6:8084/AXN/index.m3u8"),
    ("TLC [S2]", "http://138.255.2.6:8084/TVSENADO/index.m3u8"),
    ("TLC (ALTERNATIVO) [S2]", "http://45.190.28.50/TLC_HD/index.m3u8"),
    ("PARAMOUNT 2 [S2]", "http://177.52.24.163/PARAMOUNT-2-HD/index.m3u8"),
    ("PARAMOUNT 3 [S2]", "http://177.52.24.163/PARAMOUNT-3-HD/index.m3u8"),
    ("PARAMOUNT 4 [S2]", "http://177.52.24.163/PARAMOUNT-4-HD/index.m3u8"),
    ("TELECINE ACTION [S2]", "http://177.52.24.163/TELECINE-ACTION-HD/index.m3u8"),
    ("TELECINE CULT [S2]", "http://177.52.24.163/TELECINE-CULT-HD/index.m3u8"),
    ("TELECINE FUN [S2]", "http://177.52.24.163/TELECINE-FUN-HD/index.m3u8"),
    ("TELECINE PIPOCA [S2]", "http://177.52.24.163/TELECINE-PIPOCA-HD/index.m3u8"),
    ("TELECINE PREMIUM [S2]", "http://177.52.24.163/TELECINE-PREMIUM-HD/index.m3u8"),
    ("TELECINE TOUCH [S2]", "http://177.52.24.163/TELECINE-TOUCH-HD/index.m3u8"),
    ("TNT NOVELAS [S2]", "http://177.52.24.163/TELECINE-TOUCH-HD/index.m3u8"),
    ("TNT [S2]", "http://177.52.24.163/TNT-HD/index.m3u8"),
    ("TNT SERIES [S2]", "http://177.52.24.163/TNT-SERIES-HD/index.m3u8"),
    ("WARNER [S2]", "http://45.190.28.50/WARNER_HD/index.m3u8"),
    ("HBO [S2]", "http://45.190.28.50/HBO/index.m3u8"),
    ("HBO2 [S2]", "http://45.190.28.50/HBO2/index.m3u8"),
    ("HBO POP [S2]", "http://45.190.28.50/HBO_POP_HD/index.m3u8"),
    ("HBO PLUS [S2]", "http://45.190.28.50/HBO_PLUS/index.m3u8"),
    ("HBO FAMILY [S2]", "http://45.190.28.50/HBO_FAMILY/index.m3u8"),
    ("HBO SIGNATURE [S2]", "http://45.190.28.50/HBO_SIGNATURE/index.m3u8"),
    ("HBO MUNDI [S2]", "http://45.190.28.50/HBO_MUNDI_HD/index.m3u8"),
]

# --- CONFIGURAÇÃO PLUTO TV ---
PLUTO_URL = "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_br.m3u"

def fetch_link(cid):
    try:
        url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        r = session.get(url, timeout=15)
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        if match:
            return match.group(1).replace('\\/', '/').replace('\\', '')
    except: return None
    return None

def fetch_pluto():
    try:
        r = session.get(PLUTO_URL, timeout=15)
        if r.status_code == 200:
            db["pluto_cache"] = r.text
    except: pass

def preloader():
    while True:
        try:
            fetch_pluto() # Atualiza cache da Pluto TV
            if db["ids"]:
                for cid in db["ids"][:40]:
                    link = fetch_link(cid)
                    if link:
                        db["links"][cid] = {"url": link, "time": time.time()}
                    time.sleep(0.5)
            time.sleep(180)
        except: time.sleep(30)

threading.Thread(target=preloader, daemon=True).start()

@app.route('/play/<canal_id>')
def play(canal_id):
    cached = db["links"].get(canal_id)
    if cached and (time.time() - cached["time"] < 240):
        url = cached["url"]
    else:
        url = fetch_link(canal_id)
    if url:
        return redirect(url, code=302)
    return "Canal Offline", 404

@app.route('/playlist.m3u')
def m3u_route():
    base_url = request.host_url.rstrip('/')

    # 1. Canais da API MegaFlix com Sufixo [S1] - AGORA EM PRIMEIRO
    api_output = ""
    new_ids = []
    try:
        api_url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
        r = session.post(api_url, data={"userHistoric": "[]"}, timeout=20)
        content = r.text
        items = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", content)
        data_blocks = re.findall(r'data-data=["\']([^"\']+)["\']', content)

        for raw in ([d for l, d in items] + data_blocks):
            try:
                try:
                    data = json.loads(base64.b64decode(raw).decode('utf-8'))
                except:
                    data = json.loads(raw.replace('\\"', '"'))

                cid = data.get('id')
                if not cid: continue
                new_ids.append(cid)

                c_name = re.sub('<[^<]+?>', '', data.get('titulo', data.get('name', 'Canal'))).strip()
                c_name = f"{c_name} [S1]" # Adiciona sufixo [S1]
                logo = data.get('img', data.get('poster', ''))

                api_output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix [S1]",{c_name}\n'
                api_output += f'#EXTVLCOPT:network-caching=30000\n'
                api_output += f'#EXTHTTP:{{"User-Agent":"{UA_OFFICIAL}","X-Requested-With":"com.megaflix.app"}}\n'
                api_output += f"{base_url}/play/{cid}\n"
            except: continue

        if new_ids:
            db["ids"] = new_ids

    except:
        pass # Em caso de erro, segue para as próximas listas sem os canais da API

    # 2. Canais manuais [S2] - EM SEGUNDO
    manual_output = ""
    for name, link in MANUAL_CHANNELS:
        manual_output += f'#EXTINF:-1 group-title="CANAIS [S2]",{name}\n'
        manual_output += f'#EXTVLCOPT:network-caching=30000\n'
        manual_output += f'#EXTVLCOPT:http-reconnect=true\n'
        manual_output += f"{link}\n"

    # 3. Canais PLUTO TV - EM TERCEIRO
    pluto_output = ""
    pluto_data = db.get("pluto_cache") or ""
    if not pluto_data:
        try:
            r = session.get(PLUTO_URL, timeout=10)
            if r.status_code == 200:
                pluto_data = r.text
        except: pass

    if pluto_data:
        lines = pluto_data.splitlines()
        for i in range(len(lines)):
            if lines[i].startswith("#EXTINF:"):
                inf_line = lines[i]
                url_line = ""
                for j in range(i + 1, len(lines)):
                    if not lines[j].startswith("#"):
                        url_line = lines[j]
                        break

                if not url_line: continue

                if "," in inf_line:
                    parts = inf_line.rsplit(",", 1)
                    name = parts[1].strip()
                    new_inf = f"{parts[0]},{name} [PLUTO]"
                else:
                    new_inf = f"{inf_line} [PLUTO]"

                pluto_output += f"{new_inf}\n"
                pluto_output += f'#EXTVLCOPT:network-caching=30000\n'
                pluto_output += f"{url_line}\n"

    # Monta a playlist final
    full_playlist = "#EXTM3U\n" + api_output + manual_output + pluto_output
    db["last_playlist"] = full_playlist

    return Response(full_playlist, mimetype='text/plain')

@app.route('/pluto_proxy')
def pluto_proxy():
    try:
        encoded_url = request.args.get('u')
        if not encoded_url: return "URL ausente", 400
        url = base64.b64decode(encoded_url).decode()

        # O segredo é buscar o manifesto sempre com o User-Agent oficial
        # e sem deixar o player do usuário fazer cache do manifesto antigo
        r = session.get(url, headers={"User-Agent": UA_OFFICIAL}, timeout=10)

        # Ajustamos o manifesto para evitar que o player se perca
        content = r.text

        resp = Response(content, mimetype='application/vnd.apple.mpegurl')
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    except Exception as e:
        return str(e), 500

@app.route('/')
def home():
    return "Servidor V19.2 Híbrido ONLINE - RÁTIMBUM & PLUTO Adicionado"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
