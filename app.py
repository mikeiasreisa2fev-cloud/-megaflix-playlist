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

# Sessão com pool de conexões e política de retentativas
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

# Cache da Playlist (Reduzido para 5 min para garantir links mais novos)
cache_data = {"playlist": None, "expiry": 0}

def get_channels():
    if cache_data["playlist"] and time.time() < cache_data["expiry"]:
        return cache_data["playlist"]

    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    # Adicionamos propriedades que players profissionais (como IPTV Smarters ou OTT) usam para buffer
    playlist = "#EXTM3U x-tvg-url=\"\"\n"
    
    try:
        response = session.post(url, data={"userHistoric": "[]"}, timeout=10)
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
                
                # Otimização M3U: Força o player a usar o User-Agent correto e aumenta o cache de rede
                playlist += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}\n'
                playlist += f'#EXTVLCOPT:network-caching=5000\n' # 5 segundos de buffer no VLC
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

# Cache de link de streaming muito curto (60s) 
# Isso evita que você use um token que já expirou, causa principal dos travamentos
@lru_cache(maxsize=100)
def get_stream_url(canal_id, timestamp):
    try:
        ext_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"
        r = session.get(ext_url, timeout=8)
        
        m3u8 = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if m3u8: return m3u8.group(1)
        
        js = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        if js: return js.group(1)
    except:
        pass
    return None

@app.route('/play/<canal_id>')
def play(canal_id):
    # Usamos o minuto atual para o cache, assim o link é renovado a cada 60 segundos
    timestamp = int(time.time() / 60) 
    url_final = get_stream_url(canal_id, timestamp)
    
    if url_final:
        # Redireciona com código 302 (temporário) para o player não salvar o link expirado
        return redirect(url_final, code=302)
    return "Offline", 404

@app.route('/playlist.m3u')
def m3u_route():
    return Response(get_channels(), mimetype='text/plain')

@app.route('/')
def home():
    return "Sistema Ativo - Use /playlist.m3u no seu player"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
