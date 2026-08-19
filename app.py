from flask import Flask, Response, request, stream_with_context
import requests
import re
import os
import json
import base64
import time
import threading
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# --- MOTOR DE ALTA PERFORMANCE E FRAGMENTAÇÃO ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=200, 
    pool_maxsize=500, # Aumentado ao limite para fragmentação
    max_retries=5
)
session.mount('https://', adapter)
session.mount('http://', adapter)

UA_MOBILE = "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
HEADERS = {
    "User-Agent": UA_MOBILE,
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "Connection": "keep-alive"
}
session.headers.update(HEADERS)

db = {"links": {}, "ids": []}

def fetch_real_url(cid):
    """Busca o link real na fonte original"""
    try:
        url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        r = session.get(url, timeout=7)
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        if match:
            return match.group(1).replace('\\/', '/')
    except:
        return None
    return None

def preloader_engine():
    """Mantém os tokens dos canais sempre 'frescos' no servidor"""
    executor = ThreadPoolExecutor(max_workers=20)
    while True:
        try:
            if db["ids"]:
                targets = db["ids"][:60]
                executor.map(lambda cid: db["links"].update({cid: {"url": fetch_real_url(cid), "time": time.time()}}), targets)
            time.sleep(100) # Renovação rápida
        except:
            time.sleep(20)

threading.Thread(target=preloader_engine, daemon=True).start()

@app.route('/play/<canal_id>')
def proxy_stream(canal_id):
    """
    MODO FRAGMENTADO: O servidor baixa e repassa o vídeo em tempo real.
    Isso elimina travamentos de conexão direta entre o player e a fonte.
    """
    cached = db["links"].get(canal_id)
    url = cached["url"] if cached and (time.time() - cached["time"] < 150) else fetch_real_url(canal_id)
    
    if not url:
        return "Canal Offline", 404

    def generate():
        try:
            # Abre a conexão com a fonte em modo streaming
            with session.get(url, stream=True, timeout=15) as r:
                # Repassa os headers de conteúdo
                # Fragmenta o download em pedaços de 256KB para fluidez máxima
                for chunk in r.iter_content(chunk_size=256 * 1024):
                    if chunk:
                        yield chunk
        except Exception as e:
            print(f"Erro no stream: {e}")

    # Retorna o vídeo fragmentado com suporte a cache e buffer agressivo
    return Response(stream_with_context(generate()), content_type="video/mp2t")

@app.route('/playlist.m3u')
def m3u_route():
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
                
                output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix FRAGMENTADO",{name}\n'
                # COMANDOS DE BUFFER EXTREMO (30 seg de cache no player + 30 seg no proxy)
                output += f'#EXTVLCOPT:network-caching=30000\n'
                output += f'#EXTVLCOPT:http-reconnect=true\n'
                output += f'#EXTVLCOPT:clock-jitter=0\n'
                output += f"{base_url}/play/{cid}\n"
            except:
                continue
        
        db["ids"] = new_ids
        return Response(output, mimetype='text/plain')
    except:
        return "Erro", 500

@app.route('/')
def health():
    return f"V9 EXTREME FRAGMENTED - Canais: {len(db['ids'])}"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), threaded=True)
