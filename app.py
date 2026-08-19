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

# --- CONFIGURAÇÕES DE ALTA PERFORMANCE E ENGENHARIA REVERSA ---
# Pool de conexões persistentes para resposta instantânea
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=100, 
    pool_maxsize=200, 
    max_retries=3
)
session.mount('https://', adapter)
session.mount('http://', adapter)

# Headers idênticos aos do App Oficial Android para liberar qualidade máxima
APP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
    "X-Requested-With": "com.megaflix.app", # Assinatura do App Original
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "Accept": "*/*",
    "Connection": "keep-alive"
}
session.headers.update(APP_HEADERS)

# Banco de dados em memória (RAM) para cache ultra-rápido
db = {
    "links": {},  # canal_id: {"url": link, "time": timestamp}
    "ids": []
}

def get_high_quality_variant(url):
    """Analisa a lista master e seleciona a melhor resolução disponível"""
    try:
        r = session.get(url, timeout=5)
        if "#EXT-X-STREAM-INF" in r.text:
            variants = re.findall(r'RESOLUTION=(\d+x\d+).*?\n(.*?\.m3u8)', r.text)
            if variants:
                # Ordena pela maior resolução (ex: 1080p) e pega a primeira
                variants.sort(key=lambda x: int(x[0].split('x')[0]), reverse=True)
                best_link = variants[0][1]
                if not best_link.startswith("http"):
                    base = url.rsplit('/', 1)[0]
                    best_link = f"{base}/{best_link}"
                return best_link
    except:
        pass
    return url

def fetch_stream_link(cid):
    """Busca o link real de forma limpa e aplica engenharia de qualidade"""
    try:
        url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        r = session.get(url, timeout=10)
        
        # Procura o link .m3u8 ou redirecionamento JS
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        
        if match:
            raw_url = match.group(1).replace('\\/', '/').replace('\\', '')
            # Tenta forçar a resolução mais alta
            return get_high_quality_variant(raw_url)
    except:
        return None
    return None

def preloader_worker():
    """Motor de busca agressivo em segundo plano"""
    executor = ThreadPoolExecutor(max_workers=10)
    while True:
        try:
            if db["ids"]:
                # Mantém os 50 primeiros canais sempre ativos no cache
                targets = db["ids"][:50]
                for cid in targets:
                    link = fetch_stream_link(cid)
                    if link:
                        db["links"][cid] = {"url": link, "time": time.time()}
                    time.sleep(0.5) 
            time.sleep(120) # Renova tudo a cada 2 minutos
        except:
            time.sleep(30)

# Inicia o motor de pre-carregamento (Pre-download de links)
threading.Thread(target=preloader_worker, daemon=True).start()

@app.route('/play/<canal_id>')
def play(canal_id):
    """Entrega o link de alta qualidade instantaneamente do cache"""
    cached = db["links"].get(canal_id)
    
    # Se o link estiver no cache e tiver menos de 3 minutos, entrega na hora
    if cached and (time.time() - cached["time"] < 180):
        return redirect(cached["url"], code=302)
    
    # Se não estiver no cache, busca na hora (emergência)
    url = fetch_stream_link(canal_id)
    if url:
        db["links"][canal_id] = {"url": url, "time": time.time()}
        return redirect(url, code=302)
        
    return "Canal Offline", 404

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

        output = "#EXTM3U x-tvg-url=\"\"\n"
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
                
                output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix ULTRA-HD",{name}\n'
                
                # --- COMANDOS PARA ELIMINAR TRAVAMENTOS NO PLAYER ---
                output += f'#EXTVLCOPT:network-caching=30000\n' # 30 Segundos de Buffer
                output += f'#EXTVLCOPT:http-reconnect=true\n'
                output += f'#EXTHTTP:{{"User-Agent":"{APP_HEADERS["User-Agent"]}","X-Requested-With":"com.megaflix.app"}}\n'
                
                output += f"{base_url}/play/{cid}\n"
            except:
                continue
        
        db["ids"] = new_ids
        return Response(output, mimetype='text/plain')
    except:
        return "Erro ao carregar lista", 500

@app.route('/')
def home():
    return f"Servidor MegaFlix V11 ONLINE - Canais em Cache: {len(db['links'])}"

if __name__ == "__main__":
    # Render detecta a porta automaticamente
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
