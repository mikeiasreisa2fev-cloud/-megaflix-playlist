from flask import Flask, Response, redirect, request
import requests
import re
import os
import json
import base64
import time
from functools import lru_cache

app = Flask(__name__)

# --- CONFIGURAÇÃO DE ALTA PERFORMANCE ---

# Sessão com pool de conexões para resposta rápida
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=50)
session.mount('https://', adapter)
session.mount('http://', adapter)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36",
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "Accept": "*/*"
}
session.headers.update(HEADERS)

# Cache da Playlist (5 min)
cache_data = {"playlist": None, "expiry": 0}

def get_channels():
    if cache_data["playlist"] and time.time() < cache_data["expiry"]:
        return cache_data["playlist"]

    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    playlist = "#EXTM3U x-tvg-url=\"\"\n"
    
    try:
        response = session.post(url, data={"userHistoric": "[]"}, timeout=12)
        content = response.text

        items = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", content)
        data_blocks = re.findall(r'data-data=["\']([^"\']+)["\']', content)
        
        all_found = [{"link": l, "data": d} for l, d in items]
        all_found += [{"link": "", "data": d} for d in data_blocks]

        my_url = request.host_url.rstrip('/')

        for item in all_found:
            try:
                raw = item['data']
                try:
                    decoded = base64.b64decode(raw).decode('utf-8')
                    data = json.loads(decoded)
                except:
                    data = json.loads(raw.replace('\\"', '"').replace("\\'", "'"))
                
                cid = data.get('id')
                if not cid: continue
                
                name = re.sub('<[^<]+?>', '', data.get('titulo', data.get('name', 'Canal'))).strip()
                logo = data.get('img', data.get('poster', ''))
                group = data.get('genre', 'MegaFlix')

                stream_link = f"{my_url}/play/{cid}"
                
                # Tags de Buffer e Header para o Player
                playlist += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}\n'
                playlist += f'#EXTVLCOPT:network-caching=10000\n' # 10 segundos de buffer para evitar travas
                playlist += f'#EXTHTTP:{{"User-Agent":"{HEADERS["User-Agent"]}"}}\n'
                playlist += f"{stream_link}\n"
            except:
                continue

        if playlist != "#EXTM3U x-tvg-url=\"\"\n":
            cache_data["playlist"] = playlist
            cache_data["expiry"] = time.time() + 300

        return playlist
    except:
        return cache_data["playlist"] or "#EXTM3U\n# Erro ao carregar"

# Cache de link de streaming (60s) para renovar tokens expirados
@lru_cache(maxsize=100)
def get_stream_url(canal_id, timestamp):
    try:
        ext_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"
        r = session.get(ext_url, timeout=10)
        
        # Busca m3u8 e limpa barras invertidas que quebram o link
        m3u8 = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if m3u8: 
            return m3u8.group(1).replace('\\/', '/')
        
        js = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        if js: 
            return js.group(1).replace('\\/', '/')
    except:
        pass
    return None

@app.route('/play/<canal_id>')
def play(canal_id):
    # Gera um timestamp por minuto para renovar o cache
    timestamp = int(time.time() / 60) 
    url_final = get_stream_url(canal_id, timestamp)
    
    if url_final:
        # Redirecionamento 302 para garantir que o player peça um novo link se este falhar
        return redirect(url_final, code=302)
    return "Offline", 404

@app.route('/playlist.m3u')
def m3u_route():
    return Response(get_channels(), mimetype='text/plain')

@app.route('/')
def home():
    return "Sistema MegaFlix Ativo"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
