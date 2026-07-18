from flask import Flask, Response
import requests
from bs4 import BeautifulSoup
import re
import os

app = Flask(__name__)

# Headers completos para simular o comportamento exato do navegador do App
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "*/*",
    "Accept-Language": "pt-BR,pt;q=0.9"
}

def get_megaflix_channels():
    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    playlist = "#EXTM3U\n"
    
    try:
        # Enviando POST com o campo userHistoric que o app exige
        response = requests.post(url, headers=HEADERS, data={"userHistoric": "[]"}, timeout=20)
        
        if response.status_code != 200:
            return f"#EXTM3U\n# Erro: Status {response.status_code} no Servidor"

        # Usando BeautifulSoup para ler o HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # O MegaFlix organiza os canais em divs com a classe 'item'
        items = soup.find_all('div', class_='item')

        for item in items:
            try:
                # 1. Extrair o nome do canal
                title_div = item.find('div', class_='title')
                name = title_div.get_text(strip=True) if title_div else "Canal Desconhecido"
                
                # 2. Extrair a URL (fica dentro do onclick)
                # Exemplo: onclick="getSource('https://link.com', '...')"
                onclick = item.get('onclick', '')
                url_match = re.search(r"getSource\('([^']+)'", onclick)
                
                if url_match:
                    stream_url = url_match.group(1)
                    
                    # 3. Extrair a Logo (se houver)
                    preview_div = item.find('div', class_='preview')
                    logo = preview_div.get_text(strip=True) if preview_div else ""
                    
                    # Formatação M3U
                    playlist += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix TV",{name}\n'
                    playlist += f"{stream_url}\n"
            except:
                continue

        if playlist == "#EXTM3U\n":
            # Se falhou, vamos tentar capturar qualquer getSource no texto bruto
            links = re.findall(r"getSource\('([^']+)'.*?class=\"title\">(.*?)</div>", response.text, re.DOTALL)
            for link, n in links:
                playlist += f'#EXTINF:-1 group-title="MegaFlix TV",{n.strip()}\n'
                playlist += f"{link}\n"

        return playlist

    except Exception as e:
        return f"#EXTM3U\n# Erro de Conexao: {str(e)}"

@app.route('/')
def index():
    return "Servidor M3U Ativo! Use /playlist.m3u"

@app.route('/playlist.m3u')
def playlist():
    content = get_megaflix_channels()
    return Response(content, mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
