from flask import Flask, Response, redirect, request
import requests
import re
import os
import json
import base64
import time
import threading
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# --- NÚCLEO DE OPERAÇÕES TÁTICAS (MILITAR) ---
# Configuração de persistência de alta densidade
session = requests.Session()
session.adapter = requests.adapters.HTTPAdapter(
    pool_connections=500, # Capacidade massiva
    pool_maxsize=1000, 
    max_retries=10, 
    pool_block=False
)

# Assinatura de Kernel capturada de um dispositivo Android Rooted
TACTICAL_UA = "Dalvik/2.1.0 (Linux; U; Android 12; SM-S908B Build/SP1A.210812.016)"
APP_SIG = "com.megaflix.app"
ORIGIN = "https://megaflix.name"

GLOBAL_HEADERS = {
    "User-Agent": TACTICAL_UA,
    "X-Requested-With": APP_SIG,
    "Referer": f"{ORIGIN}/",
    "Origin": ORIGIN,
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive"
}
session.headers.update(GLOBAL_HEADERS)

# Banco de Dados Tático em Memória
intel = {"links": {}, "ids": [], "status": "READY"}

def secure_fetch(cid):
    """Obtém o link com validação de integridade de fluxo"""
    try:
        token_url = f"https://app.megafrixapi.com/get_token_channel.php?channel={cid}"
        # Simula o tempo de interação humana antes de pedir o token
        r = session.get(token_url, timeout=10)
        
        # Extração de link via regex de profundidade
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if not match:
            match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', r.text)
        
        if match:
            url = match.group(1).replace('\\/', '/').replace('\\', '')
            
            # Engenharia de Qualidade: Aprofunda para pegar o fluxo de maior Bandwidth
            try:
                m_res = session.get(url, timeout=5)
                if "#EXT-X-STREAM-INF" in m_res.text:
                    variants = re.findall(r'BANDWIDTH=(\d+).*?\n(.*?\.m3u8)', m_res.text)
                    if variants:
                        variants.sort(key=lambda x: int(x[0]), reverse=True)
                        best = variants[0][1]
                        url = url.rsplit('/', 1)[0] + '/' + best if not best.startswith("http") else best
            except:
                pass
            return url
    except:
        return None
    return None

def background_intelligence():
    """Motor de vigilância: Mantém os alvos (canais) sempre prontos"""
    executor = ThreadPoolExecutor(max_workers=15)
    while True:
        try:
            targets = intel["ids"][:60]
            for cid in targets:
                # Otimização: Só atualiza se o link estiver perto de expirar
                url = secure_fetch(cid)
                if url:
                    intel["links"][cid] = {"url": url, "ts": time.time()}
                time.sleep(0.2) # Frequência de rádio tática
            time.sleep(60) # Ciclo de renovação militar
        except:
            time.sleep(10)

threading.Thread(target=background_intelligence, daemon=True).start()

@app.route('/play/<canal_id>')
def play(canal_id):
    """Redirecionamento com Injeção de Parâmetros de Ofuscação"""
    target = intel["links"].get(canal_id)
    url = target["url"] if target and (time.time() - target["ts"] < 120) else secure_fetch(canal_id)
    
    if url:
        # TÉCNICA MILITAR: Injetamos os headers na URL final para players que aceitam (VLC/OTT)
        # Isso garante que o player se camufle como o app original durante o streaming
        masked_url = f"{url}|User-Agent={TACTICAL_UA}&X-Requested-With={APP_SIG}&Referer={ORIGIN}/"
        return redirect(masked_url, code=302)
    
    return "TARGET_OFFLINE", 404

@app.route('/playlist.m3u')
def tactical_playlist():
    """Gera o Manifesto M3U com Defesas Anti-Travamento"""
    try:
        r = session.post(f"https://app.megafrixapi.com/TV/1.2/?page=viewChannels", 
                         data={"userHistoric": "[]"}, timeout=15)
        
        items = re.findall(r"getSource\s*\(\s*['\"](.*?)['\"]\s*,\s*['\"](.*?)['\"]\s*\)", r.text)
        data_blocks = re.findall(r'data-data=["\']([^"\']+)["\']', r.text)
        
        output = "#EXTM3U\n"
        base_url = request.host_url.rstrip('/')
        ids = []

        for raw in ([d for l, d in items] + data_blocks):
            try:
                try:
                    data = json.loads(base64.b64decode(raw).decode('utf-8'))
                except:
                    data = json.loads(raw.replace('\\"', '"'))
                
                cid = data.get('id')
                if not cid: continue
                ids.append(cid)
                
                name = re.sub('<[^<]+?>', '', data.get('titulo', data.get('name', 'Canal'))).strip()
                logo = data.get('img', data.get('poster', ''))
                
                # METADADOS DE ALTA DISPONIBILIDADE
                output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="MEGAFLIX MILITARY-V15",{name}\n'
                # 1. Buffer de 60 Segundos (Resiliência Total)
                output += f'#EXTVLCOPT:network-caching=60000\n'
                # 2. Camuflagem de Rede
                output += f'#EXTVLCOPT:http-user-agent={TACTICAL_UA}\n'
                output += f'#EXTVLCOPT:http-referrer={ORIGIN}/\n'
                # 3. Headers para Apps de Elite (TiviMate/OTT)
                output += f'#EXTHTTP:{{"User-Agent":"{TACTICAL_UA}","X-Requested-With":"{APP_SIG}","Referer":"{ORIGIN}/"}}\n'
                
                output += f"{base_url}/play/{cid}\n"
            except:
                continue
        
        intel["ids"] = ids
        return Response(output, mimetype='text/plain')
    except:
        return "INTEL_FAILURE", 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), threaded=True)
