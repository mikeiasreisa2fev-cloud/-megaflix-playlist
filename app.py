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

# --- CONFIGURAÇÕES DE ULTRA PERFORMANCE E CONSUMO DE REDE ---
# Aumentamos o pool ao limite para garantir que nenhuma requisição fique na fila
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=200, 
    pool_maxsize=300, 
    max_retries=3
)
session.mount('https://', adapter)
session.mount('http://', adapter)

# User-Agent Premium
UA_MOBILE = "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
HEADERS = {
    "User-Agent": UA_MOBILE,
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "Accept": "*/*",
    "Connection": "keep-alive" # Mantém a rede aberta
}
session.headers.update(HEADERS)

db = {
    "playlist": "",
    "links": {},  
    "ids": []
}

def fetch_stream_link(cid):
    """Busca o link real de forma ultra-rápida com limpeza de barras"""
    try:
        url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        # Timeout otimizado para não travar o processo
        r = session.get(url, timeout=6)
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        
        if match:
            return match.group(1).replace('\\/', '/')
    except:
        return None
    return None

def preloader_worker():
    """Motor de busca agressivo: Mantém os links sempre prontos"""
    # Usamos ThreadPool para buscar vários links simultaneamente, acelerando o pre-load
    executor = ThreadPoolExecutor(max_workers=10)
    while True:
        try:
            if db["ids"]:
                targets = db["ids"][:50]
                executor.map(lambda cid: db["links"].update({cid: {"url": fetch_stream_link(cid), "time": time.time()}} if fetch_stream_link(cid) else {}), targets)
            
            # Renovação a cada 2 minutos para manter o token 'vivo'
            time.sleep(120) 
        except:
            time.sleep(30)

# Inicia o motor em segundo plano
threading.Thread(target=preloader_worker, daemon=True).start()

@app.route('/play/<canal_id>')
def play(canal_id):
    """Entrega o link instantaneamente do cache"""
    cached = db["links"].get(canal_id)
    
    if cached and cached.get("url") and (time.time() - cached["time"] < 180):
        return redirect(cached["url"], code=302)
    
    link = fetch_stream_link(canal_id)
    if link:
        db["links"][canal_id] = {"url": link, "time": time.time()}
        return redirect(link, code=302)
        
    return "Offline", 404

@app.route('/playlist.m3u')
def m3u_route():
    """Gera a playlist com comandos de CONSUMO MÁXIMO DE REDE"""
    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    try:
        r = session.post(url, data={"userHistoric": "[]"}, timeout=12)
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
                
                name = re.sub('<[^<]+?>', '', data.get('titulo', data.get('name', 'Canal'))).strip()
                logo = data.get('img', data.get('poster', ''))
                
                new_ids.append(cid)
                output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix TURBO",{name}\n'
                
                # --- COMANDOS DE CONSUMO MÁXIMO DE REDE ---
                # Aumenta o cache de rede para 30 segundos (Elimina travas de oscilação da fonte)
                output += f'#EXTVLCOPT:network-caching=30000\n' 
                # Força o player a reconectar automaticamente se a rede falhar
                output += f'#EXTVLCOPT:http-reconnect=true\n'
                # Aumenta a tolerância de jitter (instabilidade) do relógio do vídeo
                output += f'#EXTVLCOPT:clock-jitter=5000\n'
                # Usa o máximo de threads do dispositivo para decodificar o vídeo
                output += f'#EXTVLCOPT:ffmpeg-threads=4\n'
                
                output += f'#EXTHTTP:{{"User-Agent":"{UA_MOBILE}"}}\n'
                output += f"{base_url}/play/{cid}\n"
            except:
                continue
        
        db["ids"] = new_ids
        return Response(output, mimetype='text/plain')
    except:
        return "Erro na API", 500

@app.route('/')
def status():
    return f"Servidor V5 ULTRA ONLINE. Canais em Cache: {len(db['links'])}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
