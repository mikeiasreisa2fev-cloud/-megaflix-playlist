from flask import Flask, Response
import requests
import re
import os

app = Flask(__name__)

# Configurações idênticas ao aplicativo MegaFlix TV
BASE_URL = "https://app.megafrixapi.com/TV/1.2/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    "Referer": "https://megaflix.name",
    "Origin": "https://megaflix.name",
    "X-Requested-With": "XMLHttpRequest"
}

def get_megaflix_channels():
    playlist = "#EXTM3U\n"
    try:
        # O App MegaFlix usa POST para carregar as páginas
        payload = {"userHistoric": "[]"}
        response = requests.post(f"{BASE_URL}?page=viewChannels", headers=HEADERS, data=payload, timeout=15)
        
        if response.status_code != 200:
            return f"#EXTM3U\n# Erro: Servidor retornou status {response.status_code}"

        html_content = response.text
        
        # Regex melhorado para capturar os canais
        # Procura pelo padrão: getSource('URL', 'DATA') ... class="title">NOME</div>
        pattern = r"getSource\('([^']+)','[^']+'\).*?class=\"title\">(.*?)</div>"
        matches = re.findall(pattern, html_content, re.DOTALL)

        # Também tentamos buscar os logos (preview)
        logos = re.findall(r"class=\"preview\">(.*?)</div>", html_content, re.DOTALL)

        if not matches:
            return "#EXTM3U\n# Nenhum canal encontrado no HTML. Verifique os logs."

        for i, (source_url, name) in enumerate(matches):
            clean_name = re.sub('<[^<]+?>', '', name).strip() # Remove tags HTML do nome
            logo = logos[i].strip() if i < len(logos) else ""
            
            # Formatação para o Tivimate
            playlist += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MegaFlix TV",{clean_name}\n'
            playlist += f"{source_url}\n"
            
        return playlist

    except Exception as e:
        return f"#EXTM3U\n# Erro no Servidor: {str(e)}"

@app.route('/')
def index():
    return "Servidor M3U Ativo! Link da lista: /playlist.m3u"

@app.route('/playlist.m3u')
def playlist():
    m3u_content = get_megaflix_channels()
    return Response(m3u_content, mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
