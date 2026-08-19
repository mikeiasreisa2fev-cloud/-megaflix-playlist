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

# --- MOTOR DE ESTABILIDADE TÁTICA ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=150, 
    pool_maxsize=300, 
    max_retries=5
)
session.mount('https://', adapter)
session.mount('http://', adapter)

# Identidade do App Oficial (Garante o sinal sem travas)
UA_MILITARY = "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
APP_PKG = "com.megaflix.app"
ORIGIN = "https://megaflix.name"

HEADERS = {
    "User-Agent": UA_MILITARY,
    "X-Requested-With": APP_PKG,
    "Referer": f"{ORIGIN}/",
    "Origin": ORIGIN,
    "Connection": "keep-alive"
}
session.headers.update(HEADERS)

# Memória de Inteligência (RAM)
db = {"links": {}, "ids": []}

def get_best_quality(url):
    """Engenharia de Bitrate: Escolhe a maior resolução antes de enviar ao player"""
    try:
        r = session.get(url, timeout=6)
        if "#EXT-X-STREAM-INF" in r.text:
            variants = re.findall(r'BANDWIDTH=(\d+).*?\n(.*?\.m3u8)', r.text)
            if variants:
                # Ordena pela maior banda (Bandwidth)
                variants.sort(key=lambda x: int(x[0]), reverse=True)
                best = variants[0][1]
                if not best.startswith("http"):
                    base = url.rsplit('/', 1)[0]
                    best = f"{base}/{best}"
                return best
    except:
        pass
    return url

def fetch_link_secure(cid):
    """Busca o token do canal e limpa o link para compatibilidade universal"""
    try:
        url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        r = session.get(url, timeout=10)
        
        # Captura o link .m3u8 real (Limpeza de escapes)
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        
        if match:
            clean_url = match.group(1).replace('\\/', '/').replace('\\', '')
            # Otimiza a qualidade antes do play
            return get_best_quality(clean_url)
    except:
        return None
    return None

def preloader_worker():
    """Motor de Pre-aquecimento: Mantém os links prontos 24/7"""
    executor = ThreadPoolExecutor(max_workers=10)
    while True:
        try:
            if db["ids"]:
                targets = db["ids"][:50]
                for cid in targets:
                    link = fetch_link_secure(cid)
                    if link:
                        db["links"][cid] = {"url": link, "time": time.time()}
                    time.sleep(0.5)
            time.sleep(150)
        except:
            time.sleep(30)

threading.Thread(target=preloader_worker, daemon=True).start()

@app.route('/play/<canal_id>')
def play(canal_id):
    """Redirecionamento Limpo (Compatível com 100% dos Players)"""
    cached = db["links"].get(canal_id)
    
    # Se link no cache tiver menos de 3 minutos, entrega na hora
    if cached and (time.time() - cached["time"] < 180):
        url = cached["url"]
    else:
        url = fetch_link_secure(canal_id)
    
    if url:
        # Redirecionamento 302 SEM caracteres especiais (|) para não quebrar o player
        return redirect(url, code=302)
    
    return "Offline", 404

@app.route('/playlist.m3u')
def m3u_route():
    """Gera playlist M3U com Metadados Anti-Travamento"""
    try:
        r = session.post(f"{ORIGIN}/TV/1.2/?page=viewChannels", 
                         data={"userHistoric": "[]"}, timeout=12)
        
        items = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", r.text)
        data_blocks = re.findall(r'data-data=["\']([^"\']+)["\']', r.text)
        
        output = "#EXTM3U\n"
        base_url = request.host_url.rstrip('/')
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
                
                name = re.sub('<[^<]+?>', '', data.get('titulo', data.get('name', 'Canal'))).strip()
                logo = data.get('img', data.get('poster', ''))
                
                output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix PREMIUM V16",{name}\n'
                
                # --- INSTRUÇÕES DE ALTA PERFORMANCE (Buffer de 30s) ---
                output += f'#EXTVLCOPT:network-caching=30000\n'
                output += f'#EXTVLCOPT:http-user-agent={UA_MILITARY}\n'
                # Tag JSON Headers para players inteligentes (TiviMate, Smarters)
                output += f'#EXTHTTP:{{"User-Agent":"{UA_MILITARY}","X-Requested-With":"{APP_PKG}"}}\n'
                
                output += f"{base_url}/play/{cid}\n"
            except:
                continue
        
        db["ids"] = new_ids
        return Response(output, mimetype='text/plain')
    except:
        return "Erro", 500

@app.route('/')
def home():
    return f"V16 ONLINE - Inteligência Ativa"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
