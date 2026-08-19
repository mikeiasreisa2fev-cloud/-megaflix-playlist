from flask import Flask, Response, redirect, request
import requests
import re
import os
import json
import base64
import time
import threading
from urllib.parse import urljoin

app = Flask(__name__)

# --- MOTOR DE ENGENHARIA REVERSA AVANÇADA ---
session = requests.Session()
# Aumentamos o pool para gerenciar múltiplas sessões de usuários
adapter = requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=500)
session.mount('https://', adapter)

# Identidade exata capturada via Sniffer no App Original
APP_UA = "Dalvik/2.1.0 (Linux; U; Android 11; SM-G998B Build/RP1A.200720.012)"
APP_PACKAGE = "com.megaflix.app"

COMMON_HEADERS = {
    "User-Agent": APP_UA,
    "X-Requested-With": APP_PACKAGE,
    "Accept-Encoding": "gzip",
    "Connection": "keep-alive"
}

db = {"links": {}, "ids": []}

def get_best_bitrate_stream(master_url):
    """
    Engenharia de Fluxo: Abre o manifesto master e seleciona o fluxo com
    a maior largura de banda (Bandwidth) e resolução.
    """
    try:
        r = session.get(master_url, headers=COMMON_HEADERS, timeout=6)
        content = r.text
        
        # Procura por linhas de fluxo: #EXT-X-STREAM-INF:BANDWIDTH=XXXX,RESOLUTION=1920x1080
        streams = re.findall(r'BANDWIDTH=(\d+).*?RESOLUTION=(\d+x\d+).*?\n(.*?\.m3u8)', content)
        
        if streams:
            # Ordena pelo maior Bandwidth (Largura de banda)
            streams.sort(key=lambda x: int(x[0]), reverse=True)
            best_segment_list = streams[0][2]
            
            # Converte link relativo em absoluto
            return urljoin(master_url, best_segment_list)
    except:
        pass
    return master_url

def fetch_ultra_link(cid):
    """Captura o link e valida a sessão na API original"""
    try:
        # A API exige um POST simulando a entrada no canal no App
        api_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        
        # Fazemos a requisição e capturamos os cookies de sessão que a API envia
        response = session.get(api_url, headers=COMMON_HEADERS, timeout=10)
        
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', response.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', response.text)
        
        if match:
            master_link = match.group(1).replace('\\/', '/')
            # Aprofunda na lista para pegar o link HD direto
            return get_best_bitrate_stream(master_link)
    except:
        return None
    return None

def maintenance_worker():
    """Mantém o banco de dados de links sempre pronto e validado"""
    while True:
        try:
            if db["ids"]:
                # Processa os canais mais importantes com prioridade
                for cid in db["ids"][:40]:
                    link = fetch_ultra_link(cid)
                    if link:
                        db["links"][cid] = {"url": link, "time": time.time()}
                    time.sleep(0.4)
            time.sleep(90) # Renovação agressiva a cada 90s
        except:
            time.sleep(30)

threading.Thread(target=maintenance_worker, daemon=True).start()

@app.route('/play/<canal_id>')
def play(canal_id):
    """Redirecionamento Inteligente com persistência de cabeçalhos"""
    cached = db["links"].get(canal_id)
    
    if cached and (time.time() - cached["time"] < 120):
        url = cached["url"]
    else:
        url = fetch_ultra_link(canal_id)
    
    if url:
        # Nota: O redirecionamento 302 é o mais compatível para manter o User-Agent no player
        return redirect(url, code=302)
    return "Fonte Indisponível", 404

@app.route('/playlist.m3u')
def m3u_route():
    """Gera a playlist M3U com as descobertas da Engenharia Reversa"""
    try:
        r = session.post("https://app.megafrixapi.com/TV/1.2/?page=viewChannels", 
                         data={"userHistoric": "[]"}, headers=COMMON_HEADERS, timeout=12)
        
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
                
                # --- INJEÇÕES DE ENGENHARIA REVERSA NO PLAYER ---
                # 1. Buffer de 30s para evitar jitter de rede
                output += f'#EXTVLCOPT:network-caching=30000\n'
                # 2. Força o Player a se identificar como o App (Crucial para não travar)
                output += f'#EXTVLCOPT:http-user-agent={APP_UA}\n'
                output += f'#EXTVLCOPT:http-referrer=https://megaflix.name/\n'
                # 3. Cabeçalho de requisição para players que suportam JSON Headers
                output += f'#EXTHTTP:{{"User-Agent":"{APP_UA}","X-Requested-With":"{APP_PACKAGE}"}}\n'
                
                output += f"{base_url}/play/{cid}\n"
            except:
                continue
        
        db["ids"] = new_ids
        return Response(output, mimetype='text/plain')
    except:
        return "Erro", 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), threaded=True)
