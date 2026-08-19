from flask import Flask, Response, redirect, request
import requests
import re
import os
import json
import base64
import time

app = Flask(__name__)

# 1. Sessão Global (Mantém a conexão aberta, acelerando muito o tempo de resposta)
session = requests.Session()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "X-Requested-With": "XMLHttpRequest"
}
session.headers.update(HEADERS)

# Cache de Playlist para não sobrecarregar o Render
cache_playlist = {"data": None, "expires": 0}

def get_channels():
    if cache_playlist["data"] and time.time() < cache_playlist["expires"]:
        return cache_playlist["data"]

    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    playlist = "#EXTM3U\n"
    
    try:
        # Timeout curto para evitar travamento do worker
        response = session.post(url, data={"userHistoric": "[]"}, timeout=15)
        content = response.text

        # Extração de dados
        items = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", content)
        data_blocks = re.findall(r'data-data=["\']([^"\']+)["\']', content)
        
        all_found = [{"link": l, "data": d} for l, d in items]
        all_found += [{"link": "", "data": d} for d in data_blocks]

        my_url = request.host_url.rstrip('/')

        for item in all_found:
            try:
                raw = item['data']
                try:
                    # Tenta B64
                    decoded = base64.b64decode(raw).decode('utf-8')
                    data = json.loads(decoded)
                except:
                    # Tenta JSON Direto
                    data = json.loads(raw.replace('\\"', '"'))
                
                cid = data.get('id')
                if not cid: continue
                
                name = re.sub('<[^<]+?>', '', data.get('titulo', data.get('name', 'Canal'))).strip()
                logo = data.get('img', data.get('poster', ''))
                group = data.get('genre', 'MegaFlix')

                stream_link = f"{my_url}/play/{cid}"
                playlist += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}\n{stream_link}\n'
            except:
                continue

        if playlist != "#EXTM3U\n":
            cache_playlist["data"] = playlist
            cache_playlist["expires"] = time.time() + 600 # Cache de 10 min

        return playlist
    except Exception as e:
        return cache_playlist["data"] or f"#EXTM3U\n# Erro: {str(e)}"

@app.route('/play/<canal_id>')
def play(canal_id):
    """
    Obtém o link real no momento do clique. 
    Removido sufixos extras para garantir que todos os players abram.
    """
    try:
        ext_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"
        # Aumentamos o timeout para garantir que o link seja pego
        r = session.get(ext_url, timeout=12)
        
        # Procura o link .m3u8 (limpa escapes de barra)
        m3u8 = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if m3u8:
            clean_url = m3u8.group(1).replace('\\/', '/')
            return redirect(clean_url)
        
        # Fallback para redirect via JS
        js = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        if js:
            clean_url = js.group(1).replace('\\/', '/')
            return redirect(clean_url)
            
        return "Canal não encontrado no servidor original", 404
    except Exception as e:
        return f"Erro ao processar: {str(e)}", 500

@app.route('/playlist.m3u')
def m3u_route():
    return Response(get_channels(), mimetype='text/plain')

@app.route('/')
def home():
    return "Servidor MegaFlix Online - Use /playlist.m3u"

if __name__ == "__main__":
    # Render detecta automaticamente a porta
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
