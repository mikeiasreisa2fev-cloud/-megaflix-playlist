from flask import Flask, Response
import requests
import re
import os
import json

app = Flask(__name__)

# Headers de alta compatibilidade
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded"
}

def get_megaflix_list():
    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    playlist = "#EXTM3U\n"
    
    try:
        # Requisição simulando o App
        response = requests.post(url, headers=HEADERS, data={"userHistoric": "[]"}, timeout=20)
        html = response.text

        # 1. Divide o HTML por seções para manter os grupos (Filmes, Esportes, etc)
        # O MegaFlix usa 'title-section' para os nomes das categorias
        sections = re.split(r'class="title-section">', html)
        
        for section in sections[1:]:
            # Extrai o nome da categoria
            group_name = section.split('</div>')[0].strip()
            
            # 2. Busca todos os blocos de canais (item)
            # O getSource tem dois parâmetros: a URL base e um JSON com os detalhes
            # getSource('URL', 'JSON_DATA')
            channels = re.findall(r"getSource\s*\(\s*'([^']*)'\s*,\s*'([^']*)'\s*\)", section)

            for stream_url, raw_data in channels:
                try:
                    # O MegaFlix envia os dados do canal como um texto JSON no segundo parâmetro
                    # Exemplo: {"id":"123", "titulo":"HBO", "img":"..."}
                    # Como o texto pode conter aspas escapadas, vamos limpar
                    data_clean = raw_data.replace('\\"', '"')
                    
                    # Tenta extrair o Título e o ID usando busca direta de texto no JSON
                    name_match = re.search(r'"titulo":"([^"]+)"', data_clean)
                    id_match = re.search(r'"id":"?(\d+)"?', data_clean)
                    logo_match = re.search(r'"img":"([^"]+)"', data_clean)

                    name = name_match.group(1) if name_match else "Canal"
                    canal_id = id_match.group(1) if id_match else ""
                    logo = logo_match.group(1) if logo_match else ""

                    # CORREÇÃO DO LINK: Se o link estiver incompleto, nós montamos ele
                    final_url = stream_url
                    if "channel=" in final_url and (final_url.endswith("=") or canal_id not in final_url):
                        final_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"

                    # Adiciona na M3U formatada
                    playlist += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group_name}",{name}\n'
                    playlist += f"{final_url}\n"
                except:
                    continue

        if playlist == "#EXTM3U\n":
            # Caso extremo: tenta capturar apenas links que pareçam canais no texto bruto
            return f"#EXTM3U\n# Sem canais encontrados. Resposta do servidor: {len(html)} bytes."

        return playlist

    except Exception as e:
        return f"#EXTM3U\n# Erro Geral: {str(e)}"

@app.route('/')
def home():
    return "Servidor M3U MegaFlix Online! Acesse /playlist.m3u"

@app.route('/playlist.m3u')
def m3u():
    return Response(get_megaflix_list(), mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
