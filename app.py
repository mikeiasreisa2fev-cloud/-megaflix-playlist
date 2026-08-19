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

# --- CONFIGURAÇÕES DE ENGENHARIA REVERSA ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=300)
session.mount('https://', adapter)

# Identidade do App Oficial para liberar o sinal sem travas
APP_UA = "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
APP_PKG = "com.megaflix.app"

HEADERS = {
    "User-Agent": APP_UA,
    "X-Requested-With": APP_PKG,
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "Connection": "keep-alive"
}
session.headers.update(HEADERS)

db = {"links": {}, "ids": []}

def get_best_quality(url):
    """Analisa o link e garante que estamos pegando a maior resolução"""
    try:
        r = session.get(url, timeout=5)
        if "#EXT-X-STREAM-INF" in r.text:
            # Pega todas as variantes de qualidade
            variants = re.findall(r'RESOLUTION=(\d+x\d+).*?\n(.*?\.m3u8)', r.text)
            if variants:
                # Ordena pela maior resolução
                variants.sort(key=lambda x: int(x[0].split('x')[0]), reverse=True)
                best = variants[0][1]
                if not best.startswith("http"):
                    base = url.rsplit('/', 1)[0]
                    best = f"{base}/{best}"
                return best
    except:
        pass
    return url

def fetch_link(cid):
    """Busca o token do canal e limpa o link para o player"""
    try:
        url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        r = session.get(url, timeout=10)
        
        # Regex aprimorada para capturar o link m3u8 real
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        
        if match:
            clean_url = match.group(1).replace('\\/', '/').replace('\\', '')
            # Otimização: Já busca a melhor qualidade antes de enviar ao player
            return get_best_quality(clean_url)
    except:
        return None
    return None

def preloader():
    """Motor de busca agressivo para que o canal abra instantaneamente"""
    executor = ThreadPoolExecutor(max_workers=10)
    while True:
        try:
            if db["ids"]:
                for cid in db["ids"][:40]:
                    link = fetch_link(cid)
                    if link:
                        db["links"][cid] = {"url": link, "time": time.time()}
                    time.sleep(0.5)
            time.sleep(150)
        except:
            time.sleep(30)

threading.Thread(target=preloader, daemon=True).start()

@app.route('/play/<canal_id>')
def play(canal_id):
    """Redireciona para o link direto de alta qualidade"""
    cached = db["links"].get(canal_id)
    
    if cached and (time.time() - cached["time"] < 180):
        url = cached["url"]
    else:
        url = fetch_link(canal_id)
        
    if url:
        # Redirecionamento 302 limpo (Funciona em todos os players)
        return redirect(url, code=302)
    return "Canal Indisponível", 404

@app.route('/playlist.m3u')
def m3u_route():
    """Gera a playlist otimizada para qualquer App de IPTV"""
    try:
        r = session.post("https://app.megafrixapi.com/TV/1.2/?page=viewChannels", 
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
                
                output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix PREMIUM",{name}\n'
                # COMANDOS DE BUFFER E ESTABILIDADE (30 segundos de rede)
                output += f'#EXTVLCOPT:network-caching=30000\n'
                output += f'#EXTVLCOPT:http-user-agent={APP_UA}\n'
                # Tag de cabeçalho compatível com Smarters, TiviMate, OTT Navigator
                output += f'#EXTHTTP:{{"User-Agent":"{APP_UA}","X-Requested-With":"{APP_PKG}"}}\n'
                output += f"{base_url}/play/{cid}\n"
            except:
                continue
        
        db["ids"] = new_ids
        return Response(output, mimetype='text/plain')
    except:
        return "Erro", 500

@app.route('/')
def home():
    return f"V14 ONLINE - Canais: {len(db['ids'])}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
