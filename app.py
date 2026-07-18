from flask import Flask, Response
import requests
import re
import os

app = Flask(__name__)

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
        # Busca a lista de canais
        response = requests.post(url, headers=HEADERS, data={"userHistoric": "[]"}, timeout=15)
        html = response.text

        # O segredo: Identificar cada seção (Grupo) e seus respectivos canais
        # Vamos dividir o HTML por seções de categorias
        sections = re.split(r'class="title-section">', html)
        
        for section in sections[1:]: # Ignora o que vem antes da primeira seção
            # 1. Extrai o nome do Grupo (ex: Esportes, Filmes, etc)
            group_match = re.search(r'(.*?)</div>', section)
            group_name = group_match.group(1).strip() if group_match else "MegaFlix TV"

            # 2. Extrai os canais dentro DESTA seção
            # Buscamos o link e o nome que estão no mesmo bloco 'item'
            items = re.findall(r'class="item".*?getSource\(\'([^\']+)\',\'([^\']+)\'\).*?class="title">(.*?)</div>', section, re.DOTALL)

            for stream_url, data_json, name in items:
                # Limpa o nome do canal
                clean_name = re.sub('<[^<]+?>', '', name).strip()
                
                # CORREÇÃO DE LINK: Se o link vier incompleto (terminando em channel=),
                # tentamos extrair o ID do segundo parâmetro (data_json)
                if stream_url.endswith("channel=") or "channel=" not in stream_url:
                    # Tenta achar o ID dentro do JSON de dados
                    id_match = re.search(r'"id":"(\d+)"', data_json)
                    if id_match:
                        stream_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={id_match.group(1)}"

                # Adiciona à playlist formatada para Tivimate
                playlist += f'#EXTINF:-1 group-title="{group_name}",{clean_name}\n'
                playlist += f"{stream_url}\n"

        if playlist == "#EXTM3U\n":
            return "#EXTM3U\n# Erro: Servidor retornou dados, mas os canais estao em formato desconhecido."

        return playlist

    except Exception as e:
        return f"#EXTM3U\n# Erro de Conexao: {str(e)}"

@app.route('/')
def home():
    return "Servidor M3U MegaFlix Online! Use /playlist.m3u"

@app.route('/playlist.m3u')
def m3u():
    return Response(get_channels(), mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
