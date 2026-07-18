from flask import Flask, Response, redirect, request
import requests
import re
import os
import json
import base64

app = Flask(__name__)

# Headers para simular o App
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
        session = requests.Session()
        response = session.post(url, headers=HEADERS, data={"userHistoric": "[]"}, timeout=25)
        content = response.text

        # --- ESTRATÉGIA DE EXTRAÇÃO ---
        # 1. Procura por qualquer chamada getSource(url, dados) - aspas simples ou duplas
        items = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", content)
        
        # 2. Procura por atributos data-data="BASE64"
        data_blocks = re.findall(r'data-data=["\']([^"\']+)["\']', content)
        
        all_found = []

        # Processa getSource
        for link, data_raw in items:
            all_found.append({"link": link, "data": data_raw})
            
        # Processa data-data
        for data_raw in data_blocks:
            all_found.append({"link": "", "data": data_raw})

        for item in all_found:
            try:
                raw = item['data']
                # Tenta decodificar Base64 (o MegaFlix adora isso)
                try:
                    decoded = base64.b64decode(raw).decode('utf-8')
                    data = json.loads(decoded)
                except:
                    # Se não for B64, tenta tratar como JSON direto (limpando escapes)
                    data = json.loads(raw.replace('\\"', '"').replace("\\'", "'"))
                
                cid = data.get('id')
                name = data.get('titulo', data.get('name', 'Canal'))
                logo = data.get('img', data.get('poster', ''))
                group = data.get('genre', 'MegaFlix TV')

                if cid and name:
                    clean_name = re.sub('<[^<]+?>', '', name).strip()
                    my_url = request.host_url.rstrip('/')
                    # Usamos nossa rota de play para garantir que o link não expire
                    stream_link = f"{my_url}/play/{cid}"
                    
                    playlist += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{clean_name}\n'
                    playlist += f"{stream_link}\n"
            except:
                continue

        # --- FALLBACK FINAL (Busca por texto plano caso os decodificadores falhem) ---
        if playlist == "#EXTM3U\n":
            # Procura IDs e Títulos soltos no código
            raw_ids = re.findall(r'"id":"?(\d+)"?', content)
            raw_names = re.findall(r'"titulo":"([^"]+)"', content)
            for i in range(min(len(raw_ids), len(raw_names))):
                my_url = request.host_url.rstrip('/')
                playlist += f'#EXTINF:-1 group-title="MegaFlix TV",{raw_names[i]}\n'
                playlist += f"{my_url}/play/{raw_ids[i]}\n"

        if playlist == "#EXTM3U\n":
            return f"#EXTM3U\n# Erro: Layout nao reconhecido. Inicio do codigo: {content[:100]}"

        return playlist

    except Exception as e:
        return f"#EXTM3U\n# Erro de Conexao: {str(e)}"

@app.route('/play/<canal_id>')
def play(canal_id):
    try:
        # Gera o token real do MegaFlix na hora que você clica no canal
        ext_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"
        r = requests.get(ext_url, headers=HEADERS, timeout=15)
        
        # Procura o link .m3u8 real
        m3u8 = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if m3u8:
            return redirect(m3u8.group(1))
        
        # Redirecionamento direto fallback
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
