from flask import Flask, Response, redirect, request
import requests
import re
import os
import json
import base64
import time
from functools import lru_cache

app = Flask(__name__)

# --- OTIMIZAÇÕES DE PERFORMANCE ---

# 1. Sessão Global para pooling de conexões (Aumenta a velocidade de resposta)
session = requests.Session()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "X-Requested-With": "XMLHttpRequest"
}
session.headers.update(HEADERS)

# 2. Cache em memória para a Playlist (Evita gargalo de CPU no Render Free)
cache_data = {"playlist": None, "expiry": 0}
CACHE_TTL = 600  # Mantém a lista por 10 minutos

def get_channels():
    # Retorna cache se ainda for válido
    if cache_data["playlist"] and time.time() < cache_data["expiry"]:
        return cache_data["playlist"]

    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    playlist = "#EXTM3U\n"
    
    try:
        # Timeout reduzido para 12s para não travar o worker do Render
        response = session.post(url, data={"userHistoric": "[]"}, timeout=12)
        content = response.text

        # Extração otimizada
        items = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", content)
        data_blocks = re.findall(r'data-data=["\']([^"\']+)["\']', content)
        
        all_found = [{"link": l, "data": d} for l, d in items]
        all_found += [{"link": "", "data": d} for d in data_blocks]

        my_url = request.host_url.rstrip('/')

        for item in all_found:
            try:
                raw = item['data']
                try:
                    decoded = base64.b64decode(raw).decode('utf-8')
                    data = json.loads(decoded)
                except:
                    data = json.loads(raw.replace('\\"', '"').replace("\\'", "'"))
                
                cid = data.get('id')
                if not cid: continue
                
                name = re.sub('<[^<]+?>', '', data.get('titulo', data.get('name', 'Canal'))).strip()
                logo = data.get('img', data.get('poster', ''))
                group = data.get('genre', 'MegaFlix')

                stream_link = f"{my_url}/play/{cid}"
                playlist += f'#EXTINF:-1 tvg-id="{cid}" tvg-logo="{logo}" group-title="{group}",{name}\n{stream_link}\n'
            except:
                continue

        # Salva no cache
        if playlist != "#EXTM3U\n":
            cache_data["playlist"] = playlist
            cache_data["expiry"] = time.time() + CACHE_TTL

        return playlist
    except Exception as e:
        return cache_data["playlist"] or f"#EXTM3U\n# Erro de Conexao: {str(e)}"

# 3. Cache de Link de Streaming (Acelera o Playback inicial)
# Faz com que o redirecionamento para o .m3u8 final seja instantâneo
@lru_cache(maxsize=200)
def get_stream_url(canal_id):
    try:
        ext_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"
        r = session.get(ext_url, timeout=10)
        
        # Busca link direto m3u8
        m3u8 = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if m3u8: return m3u8.group(1)
        
        # Fallback para redirect via JS
        js = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        if js: return js.group(1)
    except:
        pass
    return None

@app.route('/play/<canal_id>')
def play(canal_id):
    # O uso do cache aqui elimina a espera de 2~3 segundos toda vez que o canal abre
    url_final = get_stream_url(canal_id)
    if url_final:
        return redirect(url_final)
    return "Video não encontrado", 404

@app.route('/playlist.m3u')
def m3u_route():
    return Response(get_channels(), mimetype='text/plain')

@app.route('/')
def home():
    return "Servidor MegaFlix Otimizado (Render Free)"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
