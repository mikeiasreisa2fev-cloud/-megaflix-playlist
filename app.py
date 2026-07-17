from flask import Flask, Response
import requests
import re
import os

app = Flask(__name__)

BASE_URL = "https://app.megafrixapi.com/TV/1.2/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    "Referer": "https://megaflix.name"
}

def get_megaflix_channels():
    playlist = "#EXTM3U\n"
    try:
        response = requests.get(f"{BASE_URL}?page=viewChannels", headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return "#EXTM3U\n# Erro ao acessar MegaFlix"

        pattern = r"getSource\('([^']+)','([^']+)'\).*?class=\"title\">(.*?)</div>.*?class=\"preview\">(.*?)</div>"
        matches = re.findall(pattern, response.text, re.DOTALL)

        for source_url, data_json, name, thumb in matches:
            name = name.strip()
            thumb = thumb.strip()
            playlist += f'#EXTINF:-1 tvg-logo="{thumb}" group-title="MegaFlix TV",{name}\n'
            playlist += f"{source_url}\n"
            
        return playlist
    except Exception as e:
        return f"#EXTM3U\n# Erro no Servidor: {str(e)}"

@app.route('/')
def index():
    return "Servidor M3U Ativo no Render! Use /playlist.m3u"

@app.route('/playlist.m3u')
def playlist():
    m3u_content = get_megaflix_channels()
    return Response(m3u_content, mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
