from flask import Flask, Response
import requests
import re
import os
import json
import base64

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://megaflix.name/",
    "X-Requested-With": "XMLHttpRequest"
}

def get_channels():
    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    playlist = "#EXTM3U\n"
    
    try:
        # Pega o conteúdo bruto do servidor
        response = requests.post(url, headers=HEADERS, data={"userHistoric": "[]"}, timeout=20)
        content = response.text

        # SCANNER: Busca todas as chamadas 'getSource' ignorando formatação
        # Captura o Link (Parâmetro 1) e os Dados (Parâmetro 2)
        matches = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", content)

        for stream_url, raw_data in matches:
            try:
                # O MegaFlix as vezes envia os dados em Base64, as vezes em JSON puro
                # Vamos tentar decodificar de todas as formas
                data_obj = {}
                try:
                    # Tenta Base64
                    decoded = base64.b64decode(raw_data).decode('utf-8')
                    data_obj = json.loads(decoded)
                except:
                    # Se não for b64, tenta JSON direto limpando aspas
                    clean_json = raw_data.replace('\\"', '"')
                    data_obj = json.loads(clean_json)

                # Extrai as informações do objeto
                name = data_obj.get('titulo', data_obj.get('name', 'Canal s/ Nome'))
                canal_id = data_obj.get('id', '')
                logo = data_obj.get('img', data_obj.get('poster', ''))
                group = data_obj.get('genre', 'MegaFlix TV')

                # RECONSTRUÇÃO DO LINK: Se o link vier cortado (ex: channel=), nós completamos
                if "channel=" in stream_url and not re.search(r'\d+$', stream_url):
                    stream_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={canal_id}"

                # Adiciona à lista se tiver um nome válido
                if canal_id or name:
                    playlist += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}\n'
                    playlist += f"{stream_url}\n"
            except:
                continue

        # SE O SCANNER FALHOU: Tenta busca por padrões de texto fixo
        if playlist == "#EXTM3U\n":
            # Busca IDs e Nomes que costumam estar perto um do outro
            ids = re.findall(r'"id":"(\d+)"', content)
            titulos = re.findall(r'"titulo":"([^"]+)"', content)
            for i in range(min(len(ids), len(titulos))):
                playlist += f'#EXTINF:-1 group-title="MegaFlix TV",{titulos[i]}\n'
                playlist += f"https://app.megafrixapi.com/get_token_channel.php?channel={ids[i]}\n"

        return playlist

    except Exception as e:
        return f"#EXTM3U\n# Erro de Conexao: {str(e)}"

@app.route('/')
def home():
    return "Servidor M3U Online! Use /playlist.m3u"

@app.route('/playlist.m3u')
def m3u():
    return Response(get_channels(), mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
