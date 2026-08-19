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

# --- MOTOR DE ALTA PERFORMANCE ---
# Sessão com máximo de conexões simultâneas permitidas
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=100, 
    pool_maxsize=200, 
    max_retries=3
)
session.mount('https://', adapter)
session.mount('http://', adapter)

UA_PREMIUM = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": UA_PREMIUM,
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "Connection": "keep-alive"
}
session.headers.update(HEADERS)

# Banco de dados em RAM para resposta em milissegundos
db = {"links": {}, "ids": [], "playlist": ""}

def fetch_and_cache(cid):
    """Busca o link e guarda no cache de ultra velocidade"""
    try:
        url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        # Timeout curto para não travar a fila
        r = session.get(url, timeout=5)
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        
        if match:
            clean_url = match.group(1).replace('\\/', '/')
            db["links"][cid] = {"url": clean_url, "time": time.time()}
            return True
    except:
        pass
    return False

def ultra_preloader():
    """Motor que mantém TODOS os links prontos o tempo todo"""
    executor = ThreadPoolExecutor(max_workers=15)
    while True:
        try:
            if db["ids"]:
                # Processa múltiplos canais ao mesmo tempo para máxima velocidade
                executor.map(fetch_and_cache, db["ids"][:50])
            # Renova tudo a cada 2 minutos (120s)
            time.sleep(120)
        except:
            time.sleep(10)

# Inicia o motor de busca agressiva
threading.Thread(target=ultra_preloader, daemon=True).start()

@app.route('/play/<canal_id>')
def play(canal_id):
    """Entrega instantânea. O link já estará pronto no cache."""
    cached = db["links"].get(canal_id)
    
    # Se estiver no cache, entrega em 0.001s
    if cached and (time.time() - cached["time"] < 180):
        return redirect(cached["url"], code=302)
    
    # Se falhar o cache, busca na hora (emergência)
    url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"
    try:
        r = session.get(url, timeout=8)
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if match:
            return redirect(match.group(1).replace('\\/', '/'), code=302)
    except:
        pass
        
    return "Link Expirado ou Offline", 404

@app.route('/playlist.m3u')
def m3u_route():
    """Gera playlist com comandos de CONSUMO MÁXIMO DE REDE"""
    try:
        r = session.post("https://app.megafrixapi.com/TV/1.2/?page=viewChannels", 
                         data={"userHistoric": "[]"}, timeout=10)
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
                
                output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix TURBO",{name}\n'
                
                # --- COMANDOS DE CONSUMO DE REDE AO MÁXIMO ---
                # Aumenta o cache para 30 segundos (Elimina travas de oscilação)
                output += f'#EXTVLCOPT:network-caching=30000\n' 
                # Força o player a manter a conexão aberta
                output += f'#EXTVLCOPT:http-reconnect=true\n'
                # Define o número de threads de decodificação no máximo
                output += f'#EXTVLCOPT:ffmpeg-threads=4\n'
                
                output += f"{base_url}/play/{cid}\n"
            except:
                continue
        
        db["ids"] = new_ids
        return Response(output, mimetype='text/plain')
    except:
        return "Erro", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
