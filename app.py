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
        # Busca o conteúdo do servidor
        response = requests.post(url, headers=HEADERS, data={"userHistoric": "[]"}, timeout=20)
        content = response.text

        # 1. Tenta encontrar dados codificados em Base64 (comum no MegaFlix)
        # O app usa data-data="BASE64" ou getSource('url', 'BASE64')
        encoded_blocks = re.findall(r'data-data="([^"]+)"', content)
        if not encoded_blocks:
            encoded_blocks = re.findall(r"getSource\s*\(\s*'[^']*'\s*,\s*'([^']*)'\s*\)", content)

        found_channels = []

        for block in encoded_blocks:
            try:
                # Tenta decodificar o Base64
                decoded = base64.b64decode(block).decode('utf-8')
                data = json.loads(decoded)
                
                cid = data.get('id')
                name = data.get('titulo', data.get('name'))
                logo = data.get('img', data.get('poster', ''))
                
                if cid and name:
                    found_channels.append({'id': cid, 'name': name, 'logo': logo})
            except:
                continue

        # 2. Se não achou nada em Base64, tenta busca por texto limpo (JSON simples)
        if not found_channels:
            raw_data = re.findall(r'\{[^{]*?"id":"?(\d+)"?[^{]*?"titulo":"([^"]+)"[^}]*?\}', content)
            for cid, name in raw_data:
                found_channels.append({'id': cid, 'name': name, 'logo': ''})

        # Monta a M3U final
        my_url = request.host_url.rstrip('/')
        for ch in found_channels:
            # Limpa o nome de tags HTML
            clean_name = re.sub('<[^<]+?>', '', ch['name']).strip()
            # Link que passa pelo nosso extrator
            stream_link = f"{my_url}/play/{ch['id']}"
            
            playlist += f'#EXTINF:-1 tvg-logo="{ch["logo"]}" group-title="MegaFlix TV",{clean_name}\n'
            playlist += f"{stream_link}\n"

        if playlist == "#EXTM3U\n":
            # Caso extremo de erro
            snippet = content[:200].replace('\n', ' ')
            return f"#EXTM3U\n# Erro: Nao foi possivel decifrar os canais.\n# Inicio do codigo recebido: {snippet}"

        return playlist

    except Exception as e:
        return f"#EXTM3U\n# Erro de Conexao: {str(e)}"

@app.route('/play/<canal_id>')
def play(canal_id):
    try:
        # Este link simula a geração do token do canal
        extrator_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"
        # Precisamos do Referer correto para o servidor liberar o m3u8
        res = requests.get(extrator_url, headers=HEADERS, timeout=10)
        
        # Procura o link .m3u8 real dentro do código do extrator
        m3u8_match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', res.text)
        
        if m3u8_match:
            return redirect(m3u8_match.group(1))
        
        # Se for link de redirecionamento JS
        js_match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', res.text)
        if js_match:
            return redirect(js_match.group(1))

        return "Link m3u8 nao encontrado no extrator", 404
    except:
        return "Erro no servidor de play", 500

@app.route('/playlist.m3u')
def m3u_route():
    return Response(get_channels(), mimetype='text/plain')

@app.route('/')
def home():
    return "Servidor M3U MegaFlix Online!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
