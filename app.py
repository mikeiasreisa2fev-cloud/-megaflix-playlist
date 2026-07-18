from flask import Flask, Response, redirect
import requests
import re
import os
import json

app = Flask(__name__)

# Headers para simular o App
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://megaflix.name/",
    "X-Requested-With": "XMLHttpRequest"
}

def get_channels():
    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    playlist = "#EXTM3U\n"
    
    try:
        response = requests.post(url, headers=HEADERS, data={"userHistoric": "[]"}, timeout=15)
        content = response.text

        # BUSCA POR BLOCOS (Garante que ID e Titulo fiquem juntos)
        # Procuramos por qualquer estrutura que contenha um ID e um Titulo próximos
        items = re.findall(r'\{[^{]*?"id":"(\d+)"[^{]*?"titulo":"([^"]+)"[^}]*?\}', content)

        if not items:
            # Tenta um segundo padrao se o primeiro falhar
            items = re.findall(r"getSource\s*\(\s*'[^']*'\s*,\s*'(.*?)'\s*\)", content)
            
        for item in items:
            try:
                if isinstance(item, tuple):
                    canal_id, name = item
                else:
                    # Se caiu no segundo padrao, o item e uma string de dados. Extraímos o ID e Nome.
                    data = item.replace("\\'", "'").replace('\\"', '"')
                    id_m = re.search(r'"id":"?(\d+)"?', data)
                    name_m = re.search(r'"titulo":"([^"]+)"', data)
                    if not id_m or not name_m: continue
                    canal_id = id_m.group(1)
                    name = name_m.group(1)

                # Criamos o link que passa pelo NOSSO servidor para extrair o m3u8 real
                # O Tivimate vai chamar: https://seu-app.onrender.com/play/105
                my_url = request.host_url.rstrip('/')
                stream_link = f"{my_url}/play/{canal_id}"
                
                playlist += f'#EXTINF:-1 group-title="MegaFlix TV",{name}\n'
                playlist += f"{stream_link}\n"
            except:
                continue

        if playlist == "#EXTM3U\n":
            return "#EXTM3U\n# Erro Critico: Servidor MegaFlix mudou a criptografia dos dados."

        return playlist

    except Exception as e:
        return f"#EXTM3U\n# Erro: {str(e)}"

# ROTA PARA EXTRAIR O M3U8 REAL NA HORA DO PLAY
@app.route('/play/<canal_id>')
def play(canal_id):
    try:
        # 1. Simula a chamada que o App faria para pegar o token
        extrator_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"
        res = requests.get(extrator_url, headers=HEADERS, timeout=10)
        
        # 2. Busca o link .m3u8 real dentro da pagina do extrator
        # Geralmente fica em 'file': 'http...' ou source src='...'
        m3u8_match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', res.text)
        
        if m3u8_match:
            # Redireciona o Tivimate para o link real do vídeo
            return redirect(m3u8_match.group(1))
        else:
            return "Video nao encontrado", 404
    except:
        return "Erro ao extrair video", 500

@app.route('/playlist.m3u')
def m3u():
    from flask import request
    return Response(get_channels(), mimetype='text/plain')

@app.route('/')
def home():
    return "Servidor M3U MegaFlix Ativo!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
