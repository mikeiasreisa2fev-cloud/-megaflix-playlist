from flask import Flask, Response, redirect, request
import requests
import re
import os
import json
import base64

app = Flask(__name__)

# Headers ultra-realistas
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "Accept": "*/*",
    "X-Requested-With": "XMLHttpRequest"
}

def get_channels():
    base_url = "https://app.megafrixapi.com/TV/1.2/"
    channels_url = f"{base_url}?page=viewChannels"
    playlist = "#EXTM3U\n"
    
    session = requests.Session()
    
    try:
        # 1. Simula entrada na Home para pegar Cookies de segurança
        session.get(base_url, headers=HEADERS, timeout=10)
        
        # 2. Busca a lista de canais usando a sessão com cookies
        response = session.post(channels_url, headers=HEADERS, data={"userHistoric": "[]"}, timeout=20)
        content = response.text

        # 3. Identifica Categorias (Grupos) e Canais
        # Busca por qualquer div que pareça um título de seção
        sections = re.split(r'class=["\'](?:title|name)-section["\']>', content)
        
        # Caso o site venha sem divisões claras, usamos o conteúdo todo como um grupo
        if len(sections) <= 1:
            sections = ["MegaFlix TV</div>" + content]

        my_url = request.host_url.rstrip('/')

        for section in sections[1:]:
            # Extrai o nome do grupo
            group_name = section.split('</div>')[0].strip()
            group_name = re.sub('<[^<]+?>', '', group_name) # Limpa HTML do nome do grupo

            # Busca todos os blocos de dados (Base64 ou JSON)
            # O padrão busca tanto data-data quanto getSource
            items = re.findall(r'(?:data-data|getSource\s*\(\s*\'[^\']+\'\s*,\s*)\'?"?([A-Za-z0-9+/]{40,})"?\'?\)?', section)

            for block in items:
                try:
                    # Decodifica Base64
                    decoded = base64.b64decode(block).decode('utf-8')
                    data = json.loads(decoded)
                    
                    cid = data.get('id')
                    name = data.get('titulo', data.get('name'))
                    logo = data.get('img', data.get('poster', ''))
                    
                    if cid and name:
                        clean_name = re.sub('<[^<]+?>', '', name).strip()
                        stream_link = f"{my_url}/play/{cid}"
                        
                        playlist += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group_name}",{clean_name}\n'
                        playlist += f"{stream_link}\n"
                except:
                    continue

        # Backup: Se a playlist falhou no modo organizado, tenta busca bruta por IDs
        if playlist == "#EXTM3U\n":
            raw_ids = re.findall(r'"id":"?(\d+)"?.*?"titulo":"([^"]+)"', content)
            for cid, name in raw_ids:
                stream_link = f"{my_url}/play/{cid}"
                playlist += f'#EXTINF:-1 group-title="MegaFlix TV",{name.strip()}\n'
                playlist += f"{stream_link}\n"

        return playlist
    except Exception as e:
        return f"#EXTM3U\n# Erro: {str(e)}"

@app.route('/play/<canal_id>')
def play(canal_id):
    try:
        extrator_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"
        # O extrator também precisa dos headers e possivelmente de cookies
        res = requests.get(extrator_url, headers=HEADERS, timeout=10)
        
        m3u8_match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', res.text)
        if m3u8_match:
            return redirect(m3u8_match.group(1))
        
        js_match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', res.text)
        if js_match:
            return redirect(js_match.group(1))

        return "Link não encontrado", 404
    except:
        return "Erro no extrator", 500

@app.route('/playlist.m3u')
def m3u_route():
    return Response(get_channels(), mimetype='text/plain')

@app.route('/')
def home():
    return "Servidor M3U Ativo!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
