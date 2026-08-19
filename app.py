from flask import Flask, Response, redirect, request
import requests
import re
import os
import json
import base64
import time
import threading

app = Flask(__name__)

# --- CONFIGURAÇÃO DE ELITE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=100)
session.mount('https://', adapter)

# User-Agent idêntico ao do App oficial para não ser derrubado
OFFICIAL_UA = "Dalvik/2.1.0 (Linux; U; Android 11; SM-G998B Build/RP1A.200720.012)"
HEADERS = {
    "User-Agent": OFFICIAL_UA,
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "Connection": "keep-alive"
}
session.headers.update(HEADERS)

db = {"links": {}, "ids": []}

def get_ultra_fast_link(cid):
    """Obtém o link com camuflagem de Referer"""
    try:
        # A URL da API do MegaFlix exige o token de tempo
        url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        r = session.get(url, timeout=8)
        
        # Procura m3u8 ou link direto
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        
        if match:
            link = match.group(1).replace('\\/', '/')
            # Se for m3u8, muitos players aceitam a injeção de header via pipe '|'
            # Tentamos colocar mas mantemos uma versão limpa no cache
            return link
    except:
        return None
    return None

def background_refresher():
    """Mantém os links ativos e renovados a cada 90 segundos"""
    while True:
        try:
            current_ids = db["ids"][:30] # Foca nos 30 principais
            for cid in current_ids:
                link = get_ultra_fast_link(cid)
                if link:
                    db["links"][cid] = {"url": link, "time": time.time()}
                time.sleep(0.5)
            time.sleep(90) # Renovação agressiva para o token não expirar
        except:
            time.sleep(20)

threading.Thread(target=background_refresher, daemon=True).start()

@app.route('/play/<canal_id>')
def play(canal_id):
    """Redirecionamento 307 (Temporary Redirect) - Mais estável que 302"""
    cached = db["links"].get(canal_id)
    
    # Se o link em cache tem menos de 90 segundos, ele é 'fresco'
    if cached and (time.time() - cached["time"] < 90):
        url = cached["url"]
    else:
        url = get_ultra_fast_link(canal_id)
    
    if url:
        # Algumas fontes travam se não houver o Referer. 
        # Tenta injetar o header na URL para players compatíveis (VLC/OTT)
        if ".m3u8" in url and "|" not in url:
            final_url = f"{url}|User-Agent={OFFICIAL_UA}&Referer=https://megaflix.name/"
        else:
            final_url = url
            
        return redirect(final_url, code=307)
    
    return "Link Off", 404

@app.route('/playlist.m3u')
def m3u_route():
    try:
        r = session.post("https://app.megafrixapi.com/TV/1.2/?page=viewChannels", 
                         data={"userHistoric": "[]"}, timeout=12)
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
                
                name = re.sub('<[^<]+?>', '', data.get('titulo', data.get('name', 'Canal'))).strip()
                logo = data.get('img', data.get('poster', ''))
                
                new_ids.append(cid)
                output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix ULTRA-V6",{name}\n'
                # FORÇA O PLAYER A USAR BUFFER GIGANTE
                output += f'#EXTVLCOPT:network-caching=20000\n' # 20 Segundos de Buffer
                output += f'#EXTVLCOPT:http-user-agent={OFFICIAL_UA}\n'
                output += f'#EXTVLCOPT:http-referrer=https://megaflix.name/\n'
                output += f'#EXTHTTP:{{"User-Agent":"{OFFICIAL_UA}","Referer":"https://megaflix.name/"}}\n'
                output += f"{base_url}/play/{cid}\n"
            except:
                continue
        
        db["ids"] = new_ids
        return Response(output, mimetype='text/plain')
    except:
        return "Erro", 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
