from flask import Flask, Response, redirect, request
import requests
import re
import os
import json
import base64
import time
import threading
from functools import lru_cache

app = Flask(__name__)

# --- CONFIGURAÇÃO DE ALTA PERFORMANCE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=100)
session.mount('https://', adapter)

UA_ANDROID = "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36"
HEADERS = {
    "User-Agent": UA_ANDROID,
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name"
}
session.headers.update(HEADERS)

# Armazenamento de Canais e Links Pre-carregados
db = {
    "channels": [],      # Lista de IDs
    "stream_cache": {},  # canal_id: {"url": ..., "time": ...}
    "playlist_raw": ""
}

def get_real_link(canal_id):
    """Busca o link real na API do MegaFlix"""
    try:
        url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"
        r = session.get(url, timeout=10)
        m3u8 = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if m3u8:
            return m3u8.group(1).replace('\\/', '/')
        js = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        if js:
            return js.group(1).replace('\\/', '/')
    except:
        pass
    return None

def background_preloader():
    """Motor que fica renovando os links em segundo plano para não travar"""
    print("Pre-loader iniciado...")
    while True:
        try:
            if not db["channels"]:
                time.sleep(10)
                continue
            
            # Pega os 20 primeiros canais ou os mais importantes
            for cid in db["channels"][:30]: 
                link = get_real_link(cid)
                if link:
                    db["stream_cache"][cid] = {"url": link, "time": time.time()}
                time.sleep(1) # Delay para não ser bloqueado por excesso de requisições
            
            time.sleep(180) # Reinicia o ciclo a cada 3 minutos
        except Exception as e:
            print(f"Erro no preloader: {e}")
            time.sleep(30)

# Inicia o motor em uma thread separada
threading.Thread(target=background_preloader, daemon=True).start()

def update_playlist():
    """Atualiza a lista de canais disponível"""
    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    try:
        response = session.post(url, data={"userHistoric": "[]"}, timeout=15)
        content = response.text
        
        items = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", content)
        data_blocks = re.findall(r'data-data=["\']([^"\']+)["\']', content)
        all_found = [d for l, d in items] + data_blocks

        new_playlist = "#EXTM3U\n"
        new_channels = []
        my_url = request.host_url.rstrip('/')

        for raw in all_found:
            try:
                try:
                    data = json.loads(base64.b64decode(raw).decode('utf-8'))
                except:
                    data = json.loads(raw.replace('\\"', '"'))
                
                cid = data.get('id')
                if not cid: continue
                
                name = re.sub('<[^<]+?>', '', data.get('titulo', data.get('name', 'Canal'))).strip()
                logo = data.get('img', data.get('poster', ''))
                
                new_channels.append(cid)
                new_playlist += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix",{name}\n'
                new_playlist += f'#EXTVLCOPT:network-caching=10000\n'
                new_playlist += f"{my_url}/play/{cid}\n"
            except:
                continue
        
        db["channels"] = new_channels
        db["playlist_raw"] = new_playlist
    except:
        pass

@app.route('/play/<canal_id>')
def play(canal_id):
    # Verifica se o link já foi "pre-baixado" pelo motor de busca
    cached = db["stream_cache"].get(canal_id)
    
    # Se o link está no cache e tem menos de 5 minutos, usa ele instantaneamente
    if cached and (time.time() - cached["time"] < 300):
        return redirect(cached["url"], code=302)
    
    # Se não está no cache, busca na hora (primeiro acesso)
    link = get_real_link(canal_id)
    if link:
        db["stream_cache"][canal_id] = {"url": link, "time": time.time()}
        return redirect(link, code=302)
    
    return "Canal Offline", 404

@app.route('/playlist.m3u')
def m3u_route():
    update_playlist()
    return Response(db["playlist_raw"], mimetype='text/plain')

@app.route('/')
def home():
    return "Servidor com Pre-loader Ativo"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
