from flask import Flask, Response
import requests
import re
import os

app = Flask(__name__)

# Simulação profunda de um navegador Android
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36",
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

def get_megaflix_channels():
    base_url = "https://app.megafrixapi.com/TV/1.2/"
    channels_url = f"{base_url}?page=viewChannels"
    
    session = requests.Session()
    playlist = "#EXTM3U\n"
    
    try:
        # PASSO 1: Visitar a home para estabelecer sessão e cookies
        session.get(base_url, headers=HEADERS, timeout=10)
        
        # PASSO 2: Buscar os canais (POST)
        response = session.post(
            channels_url, 
            headers=HEADERS, 
            data={"userHistoric": "[]"}, 
            timeout=15
        )
        
        content = response.text
        
        # BUSCA AGRESSIVA: Procura qualquer coisa que pareça getSource('LINK', 'DATA')
        # Captura o Link e o Nome (que costuma vir logo após no HTML)
        # O padrão abaixo busca o link dentro do getSource e tenta pegar o texto da div 'title' mais próxima
        raw_matches = re.findall(r"getSource\('([^']+)'.*?class=\"title\">(.*?)</div>", content, re.DOTALL)

        if not raw_matches:
            # Tenta um segundo padrão caso o primeiro falhe
            raw_matches = re.findall(r"class=\"item\".*?onclick=\"getSource\('([^']+)'.*?>(.*?)</div>", content, re.DOTALL)

        for stream_url, name in raw_matches:
            # Limpa tags HTML do nome do canal
            clean_name = re.sub('<[^<]+?>', '', name).strip()
            # Remove quebras de linha
            clean_name = clean_name.replace('\n', ' ').replace('\r', '')
            
            playlist += f'#EXTINF:-1 group-title="MegaFlix TV",{clean_name}\n'
            playlist += f"{stream_url}\n"

        # Se ainda assim estiver vazio, retorna o erro com o tamanho da resposta para debug
        if playlist == "#EXTM3U\n":
            return f"#EXTM3U\n# ERRO: Servidor respondeu {len(content)} bytes, mas nao achou canais.\n# Verifique se o site esta ON: {channels_url}"

        return playlist

    except Exception as e:
        return f"#EXTM3U\n# Erro de Conexao: {str(e)}"

@app.route('/')
def index():
    return "Servidor M3U Ativo! Link: /playlist.m3u"

@app.route('/playlist.m3u')
def playlist():
    content = get_megaflix_channels()
    return Response(content, mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
