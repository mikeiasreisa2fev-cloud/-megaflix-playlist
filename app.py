from flask import Flask, Response
import requests
from bs4 import BeautifulSoup
import re
import os

app = Flask(__name__)

# Headers para simular o App real
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
        # Requisicao POST (o MegaFlix exige esse metodo)
        response = requests.post(url, headers=HEADERS, data={"userHistoric": "[]"}, timeout=15)
        html = response.text

        # Analisando o HTML com BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. Tenta encontrar por secoes (Categorias)
        sections = soup.find_all(True, class_=re.compile("section|category|row"))
        
        # Se o site nao usar secoes claras, analisamos o documento inteiro
        if not sections:
            sections = [soup]

        for section in sections:
            # Tenta descobrir o nome do grupo/categoria
            group_div = section.find(True, class_=re.compile("title-section|name-section|category-title"))
            group_name = group_div.get_text(strip=True) if group_div else "MegaFlix TV"
            
            # Busca todos os itens de canais dentro desta secao
            items = section.find_all(True, class_=re.compile("item|channel-item|card"))
            
            for item in items:
                onclick = item.get('onclick', '')
                # Padrao: getSource('URL', 'DATA_JSON')
                match = re.search(r"getSource\('([^']+)','([^']+)'\)", onclick)
                
                if match:
                    stream_url = match.group(1)
                    data_json = match.group(2)
                    
                    # Captura o Nome do Canal
                    title_div = item.find(True, class_=re.compile("title|name|label"))
                    name = title_div.get_text(strip=True) if title_div else "Canal"
                    
                    # Ajuste de Link: Se o link vier vazio (ex: channel=), busca o ID no JSON
                    if "channel=" in stream_url and stream_url.endswith("="):
                        id_match = re.search(r'"id":"?(\d+)"?', data_json)
                        if id_match:
                            stream_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={id_match.group(1)}"
                    
                    # Limpa nomes com lixo HTML
                    clean_name = re.sub('<[^<]+?>', '', name).strip()
                    
                    playlist += f'#EXTINF:-1 group-title="{group_name}",{clean_name}\n'
                    playlist += f"{stream_url}\n"

        # 2. SE A PLAYLIST AINDA ESTIVER VAZIA: Faz uma busca bruta no texto
        if playlist == "#EXTM3U\n":
            # Procura qualquer getSource no texto e tenta achar o titulo do JSON
            raw_matches = re.findall(r"getSource\('([^']+)','([^']+)'\)", html)
            for link, data in raw_matches:
                name_match = re.search(r'"titulo":"([^"]+)"', data)
                name = name_match.group(1) if name_match else "Canal Extraido"
                
                if "channel=" in link and link.endswith("="):
                    id_match = re.search(r'"id":"?(\d+)"?', data)
                    if id_match:
                        link = f"https://app.megafrixapi.com/get_token_channel.php?channel={id_match.group(1)}"
                
                playlist += f'#EXTINF:-1 group-title="MegaFlix TV",{name}\n'
                playlist += f"{link}\n"

        if playlist == "#EXTM3U\n":
            return "#EXTM3U\n# Erro: O site carregou mas nao encontramos canais. O layout pode ter mudado drasticamente."

        return playlist

    except Exception as e:
        return f"#EXTM3U\n# Erro de Conexao: {str(e)}"

@app.route('/')
def home():
    return "Servidor M3U Ativo! Use /playlist.m3u no Tivimate."

@app.route('/playlist.m3u')
def m3u():
    return Response(get_channels(), mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
