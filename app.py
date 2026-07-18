from flask import Flask, Response
import requests
import re
import os

app = Flask(__name__)

# Configurações para burlar a proteção do servidor
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "X-Requested-With": "XMLHttpRequest"
}

def get_megaflix_channels():
    # URL da página de canais do MegaFlix
    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    
    playlist = "#EXTM3U\n"
    try:
        # Tenta pegar os canais via POST (como o app faz)
        response = requests.post(url, headers=HEADERS, data={"userHistoric": "[]"}, timeout=15)
        html = response.text

        # 1. Tenta encontrar canais no formato do extrator (getSource)
        # Esse regex captura: URL do canal e o Nome
        matches = re.findall(r"getSource\('([^']+)'.*?class=\"title\">(.*?)</div>", html, re.DOTALL)

        if matches:
            for stream_url, name in matches:
                # Limpa o nome (remove tags HTML como <b>, <br>, etc)
                clean_name = re.sub('<[^<]+?>', '', name).strip()
                
                # Adiciona na lista M3U
                playlist += f'#EXTINF:-1 group-title="MegaFlix TV",{clean_name}\n'
                playlist += f"{stream_url}\n"
        else:
            # 2. Caso o formato mude, tenta uma busca genérica por títulos e onclicks
            # Procura por qualquer div que tenha título e um link associado
            alt_matches = re.findall(r"class=\"item\".*?onclick=\".*?'([^']+)'.*?\".*?class=\"title\">(.*?)</div>", html, re.DOTALL)
            for stream_url, name in alt_matches:
                clean_name = re.sub('<[^<]+?>', '', name).strip()
                playlist += f'#EXTINF:-1 group-title="MegaFlix TV",{clean_name}\n'
                playlist += f"{stream_url}\n"

        # Se após as duas buscas a lista continuar vazia, avisa no log da M3U
        if playlist == "#EXTM3U\n":
            return "#EXTM3U\n# Erro: O servidor do MegaFlix retornou a pagina, mas nenhum canal foi identificado no layout."

        return playlist

    except Exception as e:
        return f"#EXTM3U\n# Erro de Conexao: {str(e)}"

@app.route('/')
def index():
    return "Servidor Online! Use o link /playlist.m3u no seu player."

@app.route('/playlist.m3u')
def playlist():
    content = get_megaflix_channels()
    return Response(content, mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
