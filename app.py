from flask import Flask, Response, redirect, request
import requests
import re
import os
import json
import base64

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://megaflix.name/",
    "X-Requested-With": "XMLHttpRequest"
}

def get_channels():
    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    playlist = "#EXTM3U\n"
    
    try:
        response = requests.post(url, headers=HEADERS, data={"userHistoric": "[]"}, timeout=20)
        content = response.text

        # Divide o HTML por seções para identificar os grupos
        sections = re.split(r'class="title-section">', content)
        
        for section in sections[1:]:
            # 1. Extrai o nome da Categoria/Grupo
            group_match = re.search(r'([^<]+)</div>', section)
            group_name = group_match.group(1).strip() if group_match else "MegaFlix TV"

            # 2. Busca canais nesta seção (Base64 ou JSON)
            items = re.findall(r'data-data="([^"]+)"', section)
            if not items:
                items = re.findall(r"getSource\s*\(\s*'[^']*'\s*,\s*'([^']*)'\s*\)", section)

            my_url = request.host_url.rstrip('/')

            for block in items:
                try:
                    # Decodifica os dados do canal
                    try:
                        decoded = base64.b64decode(block).decode('utf-8')
                        data = json.loads(decoded)
                    except:
                        data = json.loads(block.replace('\\"', '"'))
                    
                    cid = data.get('id')
                    name = data.get('titulo', data.get('name'))
                    logo = data.get('img', data.get('poster', ''))
                    
                    if cid and name:
                        clean_name = re.sub('<[^<]+?>', '', name).strip()
                        # Link intermediário para gerar o token na hora
                        stream_link = f"{my_url}/play/{cid}"
                        
                        playlist += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group_name}",{clean_name}\n'
                        playlist += f"{stream_link}\n"
                except:
                    continue

        return playlist
    except Exception as e:
        return f"#EXTM3U\n# Erro: {str(e)}"

@app.route('/play/<canal_id>')
def play(canal_id):
    try:
        extrator_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"
        res = requests.get(extrator_url, headers=HEADERS, timeout=10)
        
        # Procura o link .m3u8 real
        m3u8_match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', res.text)
        if m3u8_match:
            return redirect(m3u8_match.group(1))
        
        # Fallback para redirecionamento direto
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
    return "Servidor M3U MegaFlix Online!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
