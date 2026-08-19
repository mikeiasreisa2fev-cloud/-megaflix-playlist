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

# --- MOTOR DE ALTA VELOCIDADE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=100, 
    pool_maxsize=200, 
    max_retries=3
)
session.mount('https://', adapter)
session.mount('http://', adapter)

# User-Agent de alta compatibilidade
UA_PREMIUM = "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.74 Mobile Safari/537.36"
HEADERS = {
    "User-Agent": UA_PREMIUM,
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name"
}
session.headers.update(HEADERS)

db = {"links": {}, "ids": []}

def fetch_link(cid):
    """Busca o link real de forma limpa e rápida"""
    try:
        url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        r = session.get(url, timeout=8)
        # Extração e limpeza total de barras e escapes
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        
        if match:
            return match.group(1).replace('\\/', '/').replace('\\', '')
    except:
        return None
    return None

def background_preloader():
    """Mantém os links 'quentes' na memória RAM"""
    executor = ThreadPoolExecutor(max_workers=10)
    while True:
        try:
            if db["ids"]:
                # Atualiza os links a cada 2 minutos
                targets = db["ids"][:50]
                for cid in targets:
                    link = fetch_link(cid)
                    if link:
                        db["links"][cid] = {"url": link, "time": time.time()}
                    time.sleep(0.3) 
            time.sleep(120)
        except:
            time.sleep(30)

threading.Thread(target=background_preloader, daemon=True).start()

@app.route('/play/<canal_id>')
def play(canal_id):
    """Entrega o link instantaneamente"""
    cached = db["links"].get(canal_id)
    
    # Se o link em cache tem menos de 3 minutos, entrega na hora
    if cached and (time.time() - cached["time"] < 180):
        return redirect(cached["url"], code=302)
    
    # Se falhar o cache, busca na hora
    url = fetch_link(canal_id)
    if url:
        db["links"][canal_id] = {"url": url, "time": time.time()}
        return redirect(url, code=302)
        
    return "Canal Offline", 404

@app.route('/playlist.m3u')
def m3u_route():
    """Gera a playlist com comandos de BUFFER AGRESSIVO"""
    try:
        r = session.post("https://app.megafrixapi.com/TV/1.2/?page=viewChannels", 
                         data={"userHistoric": "[]"}, timeout=12)
        content = r.text
        items = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", content)
        data_blocks = re.findall(r'data-data=["\']([^"\']+)["\']', content)
        all_data = [d for l, d in items] + data_blocks

        output = "#EXTM3U\n"
        base_url = request.host_url.rstrip('/')
        new_ids = []

        for raw in all_data:
            try:
                try:
                    data = json.loads(base64.b64decode(raw).decode('utf-8'))
                except:
                    data = json.loads(raw.replace('\\"', '"'))
                
                cid = data.get('id')
                if not cid: continue
                new_ids.append(cid)
                
                name = re.sub('<[^<]+?>', '', data.get('titulo', data.get('name', 'Canal'))).strip()
                logo = data.get('img', data.get('poster', ''))
                
                output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix Otimizado",{name}\n'
                
                # --- COMANDOS PARA TIRAR TRAVAMENTOS NO PLAYER ---
                output += f'#EXTVLCOPT:network-caching=30000\n' # 30 seg de buffer
                output += f'#EXTVLCOPT:http-reconnect=true\n'
                output += f'#EXTHTTP:{{"User-Agent":"{UA_PREMIUM}","Referer":"https://megaflix.name/"}}\n'
                
                output += f"{base_url}/play/{cid}\n"
            except:
                continue
        
        db["ids"] = new_ids
        return Response(output, mimetype='text/plain')
    except:
        return "Erro na API", 500

@app.route('/')
def home():
    return f"V10 ONLINE - Canais: {len(db['ids'])}"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), threaded=True)
