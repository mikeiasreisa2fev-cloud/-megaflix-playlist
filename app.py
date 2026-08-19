from flask import Flask, Response, redirect, request
import requests
import re
import os
import json
import base64
import time
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Configurações de Elite
executor = ThreadPoolExecutor(max_workers=10)
session = requests.Session()

# Lista de User-Agents rotativos para evitar bloqueios
UA_ANDROID = "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36"

# Cache Inteligente
cache = {
    "playlist": None,
    "playlist_time": 0,
    "streams": {}
}

def get_headers(extra_referer=None):
    h = {
        "User-Agent": UA_ANDROID,
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Origin": "https://megaflix.name",
        "Referer": extra_referer or "https://megaflix.name/"
    }
    return h

@app.route('/play/<canal_id>')
def play(canal_id):
    """
    Rota de redirecionamento inteligente. 
    Tenta obter o link com retry automático se falhar.
    """
    def fetch_link():
        try:
            # Passo 1: Obter o token
            token_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"
            r = session.get(token_url, headers=get_headers(), timeout=7)
            
            # Passo 2: Extração agressiva (procura m3u8 ou links diretos)
            link = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
            if not link:
                link = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
            
            if link:
                return link.group(1).replace('\\/', '/')
        except:
            return None
        return None

    # Tenta obter o link (até 2 tentativas rápidas)
    stream_url = fetch_link() or fetch_link()
    
    if stream_url:
        # A MÁGICA: Adicionamos os headers diretamente na URL para players que suportam (VLC/MX/OTT)
        # Se o player não suportar, ele ignora o resto, mas se suportar, o travamento para.
        if ".m3u8" in stream_url:
            separator = "|" if "|" not in stream_url else "&"
            stream_url += f"{separator}User-Agent={UA_ANDROID}&Referer=https://megaflix.name/"
        
        return redirect(stream_url, code=302)
    
    return "Erro: Fonte Offline", 404

@app.route('/playlist.m3u')
def m3u_route():
    # Cache da playlist por 15 minutos para economizar processador no Render
    if cache["playlist"] and (time.time() - cache["playlist_time"] < 900):
        return Response(cache["playlist"], mimetype='text/plain')

    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    try:
        r = session.post(url, data={"userHistoric": "[]"}, headers=get_headers(), timeout=10)
        content = r.text
        
        # Regex de alta performance
        items = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", content)
        data_blocks = re.findall(r'data-data=["\']([^"\']+)["\']', content)
        
        all_found = []
        for l, d in items: all_found.append(d)
        for d in data_blocks: all_found.append(d)

        output = "#EXTM3U\n"
        base_url = request.host_url.rstrip('/')

        for raw in all_found:
            try:
                # Decodificação rápida
                try:
                    data = json.loads(base64.b64decode(raw).decode('utf-8'))
                except:
                    data = json.loads(raw.replace('\\"', '"'))
                
                cid = data.get('id')
                if not cid: continue
                
                name = data.get('titulo', data.get('name', 'Canal'))
                logo = data.get('img', data.get('poster', ''))
                
                # Adicionamos tags de buffer pesado aqui
                output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix", {name}\n'
                output += f'#EXTVLCOPT:http-user-agent={UA_ANDROID}\n'
                output += f'#EXTVLCOPT:http-referrer=https://megaflix.name/\n'
                output += f'#EXTVLCOPT:network-caching=8000\n'
                output += f"{base_url}/play/{cid}\n"
            except:
                continue

        cache["playlist"] = output
        cache["playlist_time"] = time.time()
        return Response(output, mimetype='text/plain')
    except:
        return "Erro ao gerar lista", 500

@app.route('/')
def health():
    return "ONLINE - V3 ULTRA", 200

if __name__ == "__main__":
    # Render usa a porta da variável de ambiente PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
