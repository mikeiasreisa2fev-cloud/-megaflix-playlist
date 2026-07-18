from flask import Flask, Response
import requests
import re
import os

app = Flask(__name__)

# Headers de um navegador Chrome Real para evitar bloqueios
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://megaflix.name/",
    "Origin": "https://megaflix.name",
    "Connection": "keep-alive"
}

def get_channels():
    url = "https://app.megafrixapi.com/TV/1.2/?page=viewChannels"
    playlist = "#EXTM3U\n"
    
    try:
        # Tenta pegar a página. Se o POST falhar, tentamos GET.
        # O MegaFlix as vezes aceita POST vazio ou com userHistoric
        response = requests.post(url, headers=HEADERS, data={"userHistoric": "[]"}, timeout=15)
        
        if len(response.text) < 500: # Se a resposta for muito curta, o POST foi bloqueado
            response = requests.get(url, headers=HEADERS, timeout=15)

        html = response.text
        
        # BUSCA TOTAL: Procura qualquer link que termine em .m3u8, .mp4, .mkv ou que esteja dentro de um getSource
        # 1. Busca por getSource(URL)
        links_getSource = re.findall(r"getSource\('([^']+)'", html)
        # 2. Busca por links diretos na página
        links_diretos = re.findall(r'(https?://[^\s"\'>]+\.(?:m3u8|mp4|mkv|ts))', html)
        
        # 3. Busca por nomes (Títulos)
        names = re.findall(r'class="title">(.*?)</div>', html)

        # Unifica os links encontrados
        all_links = list(set(links_getSource + links_diretos))
        
        if not all_links:
            # DEBUG: Se não achar nada, vamos listar o que o servidor enviou (resumo)
            return f"#EXTM3U\n# DEBUG: Resposta do servidor: {len(html)} caracteres.\n# O layout pode ter mudado."

        for i, link in enumerate(all_links):
            # Tenta associar um nome ao link, se não tiver, usa "Canal [Número]"
            name = names[i] if i < len(names) else f"Canal {i+1}"
            name = re.sub('<[^<]+?>', '', name).strip() # Limpa HTML
            
            playlist += f'#EXTINF:-1 group-title="MegaFlix TV",{name}\n'
            playlist += f"{link}\n"

        return playlist

    except Exception as e:
        return f"#EXTM3U\n# Erro de Conexao: {str(e)}"

@app.route('/')
def home():
    return "Servidor M3U ON. Link: /playlist.m3u"

@app.route('/playlist.m3u')
def m3u():
    return Response(get_channels(), mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
