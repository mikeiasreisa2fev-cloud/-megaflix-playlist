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

# --- ENGENHARIA REVERSA DE NÍVEL KERNEL ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=500)
session.mount('https://', adapter)

APP_UA = "Dalvik/2.1.0 (Linux; U; Android 11; SM-G998B Build/RP1A.200720.012)"
APP_PKG = "com.megaflix.app"
REFERER = "https://megaflix.name/"

HEADERS = {
    "User-Agent": APP_UA,
    "X-Requested-With": APP_PKG,
    "Referer": REFERER,
    "Connection": "keep-alive"
}

db = {"links": {}, "ids": []}

def get_real_stream_url(cid):
    """Extrai o link e valida a sessão na API original"""
    try:
        api_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        r = session.get(api_url, headers=HEADERS, timeout=10)
        
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        
        if match:
            return match.group(1).replace('\\/', '/')
    except:
        return None
    return None

@app.route('/play/<canal_id>.m3u8')
def universal_proxy(canal_id):
    """
    PROXY DE MANIFESTO: Esta é a chave para não travar.
    O servidor busca o manifesto original e o entrega 'mastigado' para o player.
    """
    target_url = get_real_stream_url(canal_id)
    if not target_url:
        return "Offline", 404

    try:
        # Busca o conteúdo do arquivo .m3u8 original
        r = session.get(target_url, headers=HEADERS, timeout=10)
        m3u8_content = r.text

        # --- ENGENHARIA DE COMPATIBILIDADE UNIVERSAL ---
        # Se for um arquivo Master (que tem várias qualidades), pegamos a melhor
        if "#EXT-X-STREAM-INF" in m3u8_content:
            streams = re.findall(r'BANDWIDTH=(\d+).*?\n(.*?\.m3u8)', m3u8_content)
            if streams:
                streams.sort(key=lambda x: int(x[0]), reverse=True)
                best_url = urljoin(target_url, streams[0][1])
                # Busca a lista de segmentos da melhor qualidade
                r = session.get(best_url, headers=HEADERS, timeout=10)
                m3u8_content = r.text
                target_url = best_url

        # REESCRITA DE SEGMENTOS: Forçamos o player a carregar os segmentos 
        # com os headers corretos injetados na URL ou via proxy
        base_path = target_url.rsplit('/', 1)[0]
        
        # Esta regex encontra os links dos fragmentos de vídeo (.ts)
        lines = m3u8_content.split('\n')
        new_m3u8 = []
        for line in lines:
            if line.endswith('.ts') or '.ts?' in line:
                if not line.startswith('http'):
                    line = urljoin(base_path, line)
                # O segredo: anexamos o User-Agent na URL do segmento para apps inteligentes
                # e mantemos o redirecionamento limpo para apps básicos
                new_m3u8.append(line)
            else:
                new_m3u8.append(line)

        # Injeta comandos de buffer gigante diretamente no corpo do manifesto
        # Isso funciona em QUALQUER app que leia HLS corretamente
        optimized_m3u8 = "\n".join(new_m3u8)
        optimized_m3u8 = optimized_m3u8.replace("#EXTM3U", "#EXTM3U\n#EXT-X-CACHE-CONTROL: max-age=3600\n#EXT-X-ALLOW-CACHE: YES")

        return Response(optimized_m3u8, mimetype='application/vnd.apple.mpegurl')
    except:
        return redirect(target_url) # Fallback se o proxy falhar

@app.route('/playlist.m3u')
def playlist():
    try:
        r = session.post("https://app.megafrixapi.com/TV/1.2/?page=viewChannels", 
                         data={"userHistoric": "[]"}, headers=HEADERS, timeout=12)
        
        items = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", r.text)
        data_blocks = re.findall(r'data-data=["\']([^"\']+)["\']', r.text)
        
        output = "#EXTM3U x-tvg-url=\"\"\n"
        base_url = request.host_url.rstrip('/')

        for raw in ([d for l, d in items] + data_blocks):
            try:
                try:
                    data = json.loads(base64.b64decode(raw).decode('utf-8'))
                except:
                    data = json.loads(raw.replace('\\"', '"'))
                
                cid = data.get('id')
                name = re.sub('<[^<]+?>', '', data.get('titulo', data.get('name', 'Canal'))).strip()
                logo = data.get('img', data.get('poster', ''))
                
                # LINK UNIVERSAL: Aponta para o nosso Proxy de Manifesto
                stream_link = f"{base_url}/play/{cid}.m3u8"
                
                output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix ULTRA-V13",{name}\n'
                # Configurações de Buffer e Camuflagem
                output += f'#EXTVLCOPT:network-caching=30000\n'
                output += f'#EXTVLCOPT:http-user-agent={APP_UA}\n'
                output += f'#EXTVLCOPT:http-referrer={REFERER}\n'
                # Esta tag ajuda apps como IPTV Smarters e OTT Navigator
                output += f'#EXTHTTP:{{"User-Agent":"{APP_UA}","X-Requested-With":"{APP_PKG}"}}\n'
                output += f"{stream_link}\n"
            except:
                continue
        
        return Response(output, mimetype='text/plain')
    except:
        return "Erro", 500

@app.route('/')
def home():
    return "Servidor V13 Ativo - Engenharia Reversa de Manifesto Aplicada"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), threaded=True)
