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

# --- CONFIGURAÇÕES DE ALTA DISPONIBILIDADE ---
# Pool de conexões persistentes para evitar latência de DNS/Handshake
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=100, 
    pool_maxsize=100, 
    max_retries=2
)
session.mount('https://', adapter)
session.mount('http://', adapter)

# User-Agent de dispositivo móvel Premium (mais estável para streams)
UA_MOBILE = "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
HEADERS = {
    "User-Agent": UA_MOBILE,
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "Accept": "*/*"
}
session.headers.update(HEADERS)

# Banco de dados em memória para acesso instantâneo
db = {
    "playlist": "",
    "links": {},  # canal_id: {"url": link, "time": timestamp}
    "ids": []
}

def fetch_stream_link(cid):
    """Busca o link real de forma ultra-rápida"""
    try:
        url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        r = session.get(url, timeout=7)
        # Extração precisa e limpeza de barras
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        
        if match:
            return match.group(1).replace('\\/', '/')
    except:
        return None
    return None

def preloader_worker():
    """Motor de busca em segundo plano: Mantém os links sempre 'quentes'"""
    while True:
        try:
            if db["ids"]:
                # Atualiza os primeiros 40 canais (geralmente os mais vistos)
                for cid in db["ids"][:40]:
                    link = fetch_stream_link(cid)
                    if link:
                        db["links"][cid] = {"url": link, "time": time.time()}
                    time.sleep(0.5) # Evita sobrecarga no Render
            time.sleep(120) # Repete a cada 2 minutos
        except:
            time.sleep(30)

# Inicia o pre-carregamento em segundo plano
threading.Thread(target=preloader_worker, daemon=True).start()

@app.route('/play/<canal_id>')
def play(canal_id):
    """Abertura instantânea usando cache pre-carregado"""
    cached = db["links"].get(canal_id)
    
    # Se o link foi pre-carregado há menos de 3 minutos, entrega na hora
    if cached and (time.time() - cached["time"] < 180):
        return redirect(cached["url"], code=302)
    
    # Se não está no cache, busca imediatamente
    link = fetch_stream_link(canal_id)
    if link:
        db["links"][canal_id] = {"url": link, "time": time.time()}
        return redirect(link, code=302)
        
    return "Offline", 404

@app.route('/playlist.m3u')
def m3u_route():
    """Gera a playlist com comandos de Buffer Pesado para o Player"""
    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    try:
        r = session.post(url, data={"userHistoric": "[]"}, timeout=10)
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
                output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix Otimizado",{name}\n'
                # COMANDOS DE ELITE PARA O PLAYER (Buffer de 15 segundos)
                output += f'#EXTVLCOPT:network-caching=15000\n'
                output += f'#EXTVLCOPT:http-user-agent={UA_MOBILE}\n'
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
    return f"Servidor V5 ONLINE. Canais em Cache: {len(db['links'])}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
