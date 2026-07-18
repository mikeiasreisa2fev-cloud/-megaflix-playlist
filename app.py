from flask import Flask, Response, redirect, request
import requests
import re
import os
import json
import base64

app = Flask(__name__)

# Headers idênticos ao App original
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "X-Requested-With": "XMLHttpRequest"
}

def get_channels():
    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    playlist = "#EXTM3U\n"
    
    try:
        # Criamos uma nova sessão para cada pedido para evitar cookies expirados
        session = requests.Session()
        # Faz um POST com dados vazios para simular o clique no menu
        response = session.post(url, headers=HEADERS, data={"userHistoric": "[]"}, timeout=25)
        content = response.text

        # 1. BUSCA POR BLOCOS DE DADOS (Base64)
        # O MegaFlix costuma esconder os canais em strings longas de Base64
        blocks = re.findall(r'([A-Za-z0-9+/]{50,}=*)', content)
        
        extracted_count = 0
        for b in blocks:
            try:
                decoded = base64.b64decode(b).decode('utf-8')
                if '"id"' in decoded and '"titulo"' in decoded:
                    data = json.loads(decoded)
                    cid = data.get('id')
                    name = data.get('titulo')
                    logo = data.get('img', '')
                    group = data.get('genre', 'MegaFlix TV')
                    
                    if cid and name:
                        clean_name = re.sub('<[^<]+?>', '', name).strip()
                        my_url = request.host_url.rstrip('/')
                        playlist += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{clean_name}\n'
                        playlist += f"{my_url}/play/{cid}\n"
                        extracted_count += 1
            except:
                continue

        # 2. BUSCA POR TEXTO PLANO (Caso o Base64 falhe)
        if extracted_count == 0:
            raw_items = re.findall(r'"id":"?(\d+)"?.*?"titulo":"([^"]+)"', content)
            for cid, name in raw_items:
                my_url = request.host_url.rstrip('/')
                playlist += f'#EXTINF:-1 group-title="MegaFlix TV",{name.strip()}\n'
                playlist += f"{my_url}/play/{cid}\n"
                extracted_count += 1

        # 3. DIAGNÓSTICO DE ERRO (Se a lista continuar vazia)
        if playlist == "#EXTM3U\n":
            return f"#EXTM3U\n# DEBUG: Recebido {len(content)} bytes.\n# Status: {response.status_code}\n# Verifique se o app MegaFlix esta funcionando agora."

        return playlist

    except Exception as e:
        return f"#EXTM3U\n# Erro de Conexao: {str(e)}"

@app.route('/play/<canal_id>')
def play(canal_id):
    try:
        # Gera o token real na hora do play
        ext_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"
        r = requests.get(ext_url, headers=HEADERS, timeout=10)
        
        # Procura o link .m3u8 real dentro do código do extrator
        m3u8 = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if m3u8:
            return redirect(m3u8.group(1))
        
        # Redirecionamento JS fallback
        js = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        if js:
            return redirect(js.group(1))
            
        return "Video não encontrado", 404
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
