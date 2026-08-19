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
adapter = requests.adapters.HTTPAdapter(pool_connections=150, pool_maxsize=300, max_retries=5)
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

db = {"links": {}, "ids": [], "last_playlist": ""}

# --- LISTA MANUAL [S2] ATUALIZADA ---
MANUAL_CHANNELS = [
    ("CAZE TV [S2]", "http://177.52.24.163/CAZE-TV/index.m3u8"),
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
    ("ESPN 2 [S2]", "http://177.52.24.163/ESPN-2-HD/index.m3u8"),
    ("ESPN 3 [S2]", "http://177.52.24.163/ESPN-3-HD/index.m3u8"),
    ("ESPN 4 [S2]", "http://177.52.24.163/ESPN-4-HD/index.m3u8"),
    ("ESPN 5 [S2]", "http://177.52.24.163/ESPN-5-HD/index.m3u8"),
    ("SPORTYNET 1 [S2]", "http://177.52.24.163/SPORTYNET-1-HD/index.m3u8"),
    ("SPORTYNET 2 [S2]", "http://177.52.24.163/SPORTYNET-2-HD/index.m3u8"),
    ("SPORTYNET 3 [S2]", "http://177.52.24.163/SPORTYNET-3-HD/index.m3u8"),
    ("GE TV [S2]", "http://177.52.24.163/GETV-HD/index.m3u8"),
    ("TLC [S2]", "http://138.255.2.6:8084/TVSENADO/index.m3u8"),
    ("HISTORY CHANNEL [S2]", "http://177.52.24.163/HISTORY-HD/index.m3u8"),
    ("DISCOVERY CHANNEL [S2]", "http://177.52.24.163/DISCOVERY-CHANNEL-HD/index.m3u8"),
    ("DISCOVERY SCIENCE [S2]", "http://177.52.24.163/DISCOVERY-SCIENCE-HD/index.m3u8"),
    ("DISCOVERY TURBO [S2]", "http://177.52.24.163/DISCOVERY-TURBO-HD/index.m3u8"),
    ("DISCOVERY WORLD [S2]", "http://177.52.24.163/DISCOVERY-WORLD-HD/index.m3u8"),
    ("DICOVERY HOME & HEALT [S2]", "http://177.52.24.163/DISCOVERY-HH-HD/index.m3u8"),
    ("ANIMAL PLANET [S2]", "http://138.255.2.6:8084/ANIMALPLANET/index.m3u8"),
    ("LIFETIME [S2]", "http://138.255.2.6:8084/LIFETIME/index.m3u8"),
    ("SPACE [S2]", "http://138.255.2.6:8084/SPACE/index.m3u8"),
    ("MEGAPIX [S2]", "http://177.52.24.163/MEGAPIX-HD/index.m3u8"),
    ("AXN [S2]", "http://138.255.2.6:8084/AXN/index.m3u8"),
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
]

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

def preloader():
    while True:
        try:
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
    output = "#EXTM3U\n"
    base_url = request.host_url.rstrip('/')
    
    # 1. Canais manuais [S2] com Buffer Turbo de 30s
    for name, link in MANUAL_CHANNELS:
        output += f'#EXTINF:-1 group-title="CANAIS [S2]",{name}\n'
        output += f'#EXTVLCOPT:network-caching=30000\n'
        output += f'#EXTVLCOPT:http-reconnect=true\n'
        output += f"{link}\n"

    # 2. Canais da API com Camuflagem de App
    try:
        api_url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
        r = session.post(api_url, data={"userHistoric": "[]"}, timeout=20)
        content = r.text
        
        items = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", content)
        data_blocks = re.findall(r'data-data=["\']([^"\']+)["\']', content)
        
        new_ids = []
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
                logo = data.get('img', data.get('poster', ''))
                
                output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix Otimizado",{c_name}\n'
                output += f'#EXTVLCOPT:network-caching=30000\n'
                output += f'#EXTHTTP:{{"User-Agent":"{UA_OFFICIAL}","X-Requested-With":"com.megaflix.app"}}\n'
                output += f"{base_url}/play/{cid}\n"
            except: continue
        
        if new_ids:
            db["ids"] = new_ids
            db["last_playlist"] = output

    except:
        if db["last_playlist"]:
            return Response(db["last_playlist"], mimetype='text/plain')
            
    return Response(output, mimetype='text/plain')

@app.route('/')
def home():
    return "Servidor V18.1 Híbrido ONLINE - CAZE TV Adicionada"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
