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

# --- CONFIGURAÇÕES DE RECONECTIVIDADE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=200, max_retries=5)
session.mount('https://', adapter)

# Identidade Oficial do App (Engenharia Reversa)
UA_OFFICIAL = "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
HEADERS = {
    "User-Agent": UA_OFFICIAL,
    "X-Requested-With": "com.megaflix.app",
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "Connection": "keep-alive"
}
session.headers.update(HEADERS)

# Cache de Memória
db = {"links": {}, "ids": [], "last_playlist": ""}

def get_best_quality(url):
    """Garante que o link entregue seja o de maior resolução"""
    try:
        r = session.get(url, timeout=7, verify=True)
        if "#EXT-X-STREAM-INF" in r.text:
            variants = re.findall(r'BANDWIDTH=(\d+).*?\n(.*?\.m3u8)', r.text)
            if variants:
                variants.sort(key=lambda x: int(x[0]), reverse=True)
                best = variants[0][1]
                return urljoin(url, best) if not best.startswith("http") else best
    except: pass
    return url

def fetch_link(cid):
    """Busca o link do canal na API Oficial"""
    try:
        # URL CORRIGIDA PARA A API
        url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        r = session.get(url, timeout=15) # Aumentado timeout para evitar erro no Render
        
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        
        if match:
            return match.group(1).replace('\\/', '/').replace('\\', '')
    except: return None
    return None

def preloader():
    """Motor de fundo para deixar o play instantâneo"""
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
    """Redirecionamento compatível com qualquer App IPTV"""
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
    """Gera a lista M3U. Se a API falhar, retorna a última lista válida (Anti-Erro)"""
    try:
        # URL DA API CORRIGIDA
        api_url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
        r = session.post(api_url, data={"userHistoric": "[]"}, timeout=20)
        content = r.text
        
        items = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", content)
        data_blocks = re.findall(r'data-data=["\']([^"\']+)["\']', content)
        
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
                
                output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix Otimizado",{name}\n'
                output += f'#EXTVLCOPT:network-caching=30000\n'
                output += f'#EXTHTTP:{{"User-Agent":"{UA_OFFICIAL}","X-Requested-With":"com.megaflix.app"}}\n'
                output += f"{base_url}/play/{cid}\n"
            except: continue
        
        if new_ids:
            db["ids"] = new_ids
            db["last_playlist"] = output # Salva para caso de erro futuro
            return Response(output, mimetype='text/plain')
        
    except Exception as e:
        # Se der erro, tenta entregar a última lista que funcionou
        if db["last_playlist"]:
            return Response(db["last_playlist"], mimetype='text/plain')
            
    return "Erro ao conectar com a API original. Tente novamente em instantes.", 503

@app.route('/')
def home():
    return "Servidor V17 ONLINE - Lista Corrigida"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
