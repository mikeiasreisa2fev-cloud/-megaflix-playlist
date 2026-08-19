from flask import Flask, Response, redirect, request
import requests
import re
import os
import json
import base64
import time
import threading

app = Flask(__name__)

# --- CONFIGURAÇÃO DE ALTA PERFORMANCE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=100)
session.mount('https://', adapter)
session.mount('http://', adapter)

# User-Agent estável (Simulando Chrome no Android)
UA_CLEAN = "Mozilla/5.0 (Linux; Android 10; SM-A505G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"

HEADERS = {
    "User-Agent": UA_CLEAN,
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name"
}
session.headers.update(HEADERS)

# Memória de Links e IDs
db = {"links": {}, "ids": []}

def get_stream_link(cid):
    """Busca o link real de forma limpa"""
    try:
        url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        r = session.get(url, timeout=10)
        
        # Procura m3u8 ou link de redirecionamento
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        
        if match:
            # Limpa as barras invertidas (ESSENCIAL para o player funcionar)
            return match.group(1).replace('\\/', '/')
    except:
        return None
    return None

def preloader_engine():
    """Renova os links em segundo plano para que o 'Play' seja instantâneo"""
    while True:
        try:
            targets = db["ids"][:40] # Foca nos 40 principais canais
            for cid in targets:
                link = get_stream_link(cid)
                if link:
                    db["links"][cid] = {"url": link, "time": time.time()}
                time.sleep(1) # Delay suave
            time.sleep(180) # Reinicia o ciclo a cada 3 minutos
        except:
            time.sleep(30)

# Inicia o pre-carregamento
threading.Thread(target=preloader_engine, daemon=True).start()

@app.route('/play/<canal_id>')
def play(canal_id):
    """Entrega o link direto sem caracteres especiais que quebram o player"""
    cached = db["links"].get(canal_id)
    
    # Se tiver link no cache com menos de 5 minutos, usa ele
    if cached and (time.time() - cached["time"] < 300):
        return redirect(cached["url"], code=302)
    
    # Se não, busca na hora
    url = get_stream_link(canal_id)
    if url:
        db["links"][canal_id] = {"url": url, "time": time.time()}
        return redirect(url, code=302)
    
    return "Canal Offline", 404

@app.route('/playlist.m3u')
def m3u_route():
    """Gera playlist compatível com TODOS os players"""
    try:
        r = session.post("https://app.megafrixapi.com/TV/1.2/?page=viewChannels", 
                         data={"userHistoric": "[]"}, timeout=15)
        content = r.text
        
        items = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", content)
        data_blocks = re.findall(r'data-data=["\']([^"\']+)["\']', content)
        
        playlist = "#EXTM3U\n"
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
                
                name = re.sub('<[^<]+?>', '', data.get('titulo', data.get('name', 'Canal'))).strip()
                logo = data.get('img', data.get('poster', ''))
                
                new_ids.append(cid)
                playlist += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix Otimizado",{name}\n'
                # Instrução de Buffer (VLC e players avançados)
                playlist += f'#EXTVLCOPT:network-caching=10000\n'
                # Link de reprodução através do seu servidor
                playlist += f"{base_url}/play/{cid}\n"
            except:
                continue
        
        db["ids"] = new_ids
        return Response(playlist, mimetype='text/plain')
    except:
        return "Erro ao carregar lista", 500

@app.route('/')
def home():
    return f"ONLINE - Canais Ativos: {len(db['ids'])}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
