from flask import Flask, render_template, request, send_file, jsonify, after_this_request
import yt_dlp
import os
import uuid
import threading
import time
from pathlib import Path
import subprocess
import sys
import re
from urllib.parse import urlparse, parse_qs
from collections import deque
import tempfile

COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-us,en;q=0.5',
}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu-clave-secreta'
app.config['TEMPLATES_AUTO_RELOAD'] = True

DOWNLOAD_FOLDER = Path(__file__).parent / 'downloads'
DOWNLOAD_FOLDER.mkdir(exist_ok=True)

TEMP_FOLDER = Path(__file__).parent / 'temp'
TEMP_FOLDER.mkdir(exist_ok=True)

MAX_CONCURRENT = 2
download_semaphore = threading.BoundedSemaphore(MAX_CONCURRENT)
queue_lock = threading.Lock()
download_queue = deque()
descargas_activas = {}

def _inicializar_cookies():
    import base64

    local = Path(__file__).parent / 'cookies.txt'
    if local.exists() and local.stat().st_size > 100:
        try:
            contenido = local.read_text(encoding='utf-8')
            if 'youtube.com' in contenido:
                print(f"[cookies] usando archivo local: {local}")
                return str(local)
        except:
            pass

    secret = os.environ.get('COOKIE_FILE_PATH', '/etc/secrets/cookies.txt')
    if os.path.exists(secret) and os.path.getsize(secret) > 100:
        try:
            with open(secret, 'r', encoding='utf-8') as f:
                if 'youtube.com' in f.read():
                    print(f"[cookies] usando secret file: {secret}")
                    return secret
        except:
            pass

    env_cookies = os.environ.get('COOKIES_B64')
    if env_cookies:
        try:
            contenido = base64.b64decode(env_cookies).decode('utf-8')
            if 'youtube.com' in contenido:
                tmp = Path(tempfile.gettempdir()) / f'yt_cookies_{os.getpid()}.txt'
                tmp.write_text(contenido, encoding='utf-8')
                print(f"[cookies] usando env var, temp: {tmp}")
                return str(tmp)
        except Exception as e:
            print(f"[cookies] error decodificando env var: {e}")

    print("[cookies] NO hay cookies disponibles")
    return None

_COOKIE_PATH = _inicializar_cookies()

def _cookies_disponibles():
    return _COOKIE_PATH is not None

BASE_EXTRACTOR_ARGS = {
    'youtube': {
        'player_client': ['android', 'web', 'web_creator'],
    },
}

def _ydl_base_opts():
    opts = {
        'quiet': True,
        'no_warnings': True,
        'http_headers': COMMON_HEADERS,
        'extract_flat': False,
        'extractor_args': BASE_EXTRACTOR_ARGS,
    }
    opts['js_runtimes'] = {'node': {}}
    opts['remote_components'] = ['ejs:github']
    if _cookies_disponibles():
        opts['cookiefile'] = _COOKIE_PATH
    return opts

def verificar_ffmpeg():
    if 'RENDER' in os.environ:
        return False
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True)
        return True
    except:
        return False

def obtener_info_video(url):
    url_lower = url.lower()

    if 'spotify.com' in url_lower:
        return {
            'success': False,
            'error': 'Spotify usa proteccion DRM y NO se puede descargar.\n\nAlternativas:\nBusca la cancion en YouTube y usa ese enlace\nUsa la aplicacion oficial de Spotify para descargar (solo Premium)'
        }

    if 'netflix.com' in url_lower:
        return {
            'success': False,
            'error': 'Netflix usa proteccion DRM y NO se puede descargar.\n\nUsa la aplicacion oficial de Netflix para descargas offline.'
        }

    if 'primevideo.com' in url_lower or 'amazon.com' in url_lower and 'video' in url_lower:
        return {
            'success': False,
            'error': 'Amazon Prime Video usa proteccion DRM y NO se puede descargar.\n\nUsa la aplicacion oficial de Prime Video para descargas offline.'
        }

    if 'disneyplus.com' in url_lower:
        return {
            'success': False,
            'error': 'Disney+ usa proteccion DRM y NO se puede descargar.\n\nUsa la aplicacion oficial de Disney+ para descargas offline.'
        }

    if 'hbomax.com' in url_lower or 'max.com' in url_lower:
        return {
            'success': False,
            'error': 'HBO Max usa proteccion DRM y NO se puede descargar.'
        }

    ydl_opts = _ydl_base_opts()

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        error_msg = str(e)
        if 'Sign in' in error_msg:
            error_msg = 'YouTube requiere verificacion. Las cookies expiraron o Render esta bloqueado. Prueba exportar cookies frescas desde tu navegador.'
        elif 'DRM' in error_msg:
            return {
                'success': False,
                'error': 'Este sitio usa proteccion DRM y no permite descargas.\n\nPrueba con YouTube, Vimeo, Dailymotion o SoundCloud.'
            }
        return {
            'success': False,
            'error': f'Error: {error_msg}'
        }

    formatos_video = []

    for f in info.get('formats', []):
        formato = {
            'format_id': f.get('format_id'),
            'ext': f.get('ext'),
            'resolution': f.get('resolution', 'N/A'),
            'filesize': f.get('filesize'),
            'vcodec': f.get('vcodec'),
            'acodec': f.get('acodec'),
        }

        if formato['vcodec'] != 'none' and formato['resolution'] != 'N/A':
            if formato['filesize']:
                formato['filesize_mb'] = round(formato['filesize'] / (1024 * 1024), 2)
            else:
                formato['filesize_mb'] = 'N/A'
            formatos_video.append(formato)

    if not formatos_video:
        formatos_video.append({
            'format_id': 'best',
            'ext': 'mp4',
            'resolution': 'Mejor calidad',
            'filesize_mb': 'N/A',
        })

    formatos_video.sort(key=lambda x: x.get('resolution', '0p'), reverse=True)

    return {
        'success': True,
        'titulo': info.get('title', 'Sin titulo'),
        'duracion': info.get('duration', 0),
        'thumbnail': info.get('thumbnail', ''),
        'formatos_video': formatos_video[:10],
        'plataforma': 'youtube' if 'youtube.com' in url or 'youtu.be' in url else 'compatible'
    }

def descargar_video(url, formato_id, es_audio=False, callback_id=None):
    nombre_archivo = str(uuid.uuid4())
    ffmpeg_disponible = verificar_ffmpeg()

    base_opts = _ydl_base_opts()
    base_opts['outtmpl'] = str(DOWNLOAD_FOLDER / f'{nombre_archivo}.%(ext)s')
    base_opts['progress_hooks'] = [lambda d: hook_progreso(d, callback_id)]

    if es_audio:
        if ffmpeg_disponible:
            ydl_opts = {
                **base_opts,
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
        else:
            ydl_opts = {
                **base_opts,
                'format': 'bestaudio/best',
            }
    else:
        ydl_opts = {
            **base_opts,
            'format': formato_id if formato_id else 'best',
            'merge_output_format': 'mp4',
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            archivo_generado = ydl.prepare_filename(info)

            if es_audio and not ffmpeg_disponible:
                archivo_sin_ext = archivo_generado.rsplit('.', 1)[0]
                archivo_mp3 = archivo_sin_ext + '.mp3'
                if archivo_generado != archivo_mp3:
                    os.rename(archivo_generado, archivo_mp3)
                    archivo_generado = archivo_mp3
            elif es_audio and ffmpeg_disponible:
                archivo_generado = archivo_generado.rsplit('.', 1)[0] + '.mp3'

            return {
                'success': True,
                'archivo': archivo_generado,
                'nombre': info.get('title', 'video')
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def hook_progreso(d, callback_id):
    if callback_id and callback_id in descargas_activas:
        if d['status'] == 'downloading':
            if 'total_bytes' in d:
                porcentaje = (d['downloaded_bytes'] / d['total_bytes']) * 100
                descargas_activas[callback_id]['progreso'] = porcentaje
            elif 'total_bytes_estimate' in d:
                porcentaje = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
                descargas_activas[callback_id]['progreso'] = porcentaje
        elif d['status'] == 'finished':
            descargas_activas[callback_id]['progreso'] = 100
            descargas_activas[callback_id]['completado'] = True

def _procesar_siguiente():
    with queue_lock:
        if not download_queue:
            return
        download_id = download_queue.popleft()
        item = descargas_activas.get(download_id)
        if not item or item['status'] != 'queued':
            return
        item['status'] = 'downloading'

    def worker(did, url, fmt, audio):
        try:
            download_semaphore.acquire()
            resultado = descargar_video(url, fmt, audio, did)
            if did in descargas_activas:
                descargas_activas[did]['resultado'] = resultado
                descargas_activas[did]['completado'] = True
        finally:
            download_semaphore.release()
            _procesar_siguiente()

    t = threading.Thread(target=worker, args=(download_id, item['url'], item['formato_id'], item['es_audio']))
    t.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_info', methods=['POST'])
def get_info():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL no proporcionada'}), 400

    info = obtener_info_video(url)
    return jsonify(info)

@app.route('/download', methods=['POST'])
def download():
    url = request.json.get('url')
    formato_id = request.json.get('formato_id')
    es_audio = request.json.get('es_audio', False)

    if not url:
        return jsonify({'error': 'URL no proporcionada'}), 400

    download_id = str(uuid.uuid4())

    descargas_activas[download_id] = {
        'status': 'queued',
        'progreso': 0,
        'completado': False,
        'resultado': None,
        'url': url,
        'formato_id': formato_id,
        'es_audio': es_audio,
    }

    with queue_lock:
        en_cola = sum(1 for d in descargas_activas.values() if d['status'] == 'queued')
        posicion = en_cola
        download_queue.append(download_id)

    # Si hay slots libres, arranca inmediato
    with queue_lock:
        activos = sum(1 for d in descargas_activas.values() if d['status'] == 'downloading')
    if activos < MAX_CONCURRENT:
        _procesar_siguiente()
        posicion = 0

    return jsonify({'download_id': download_id, 'posicion': posicion})

@app.route('/progress/<download_id>')
def progress(download_id):
    if download_id not in descargas_activas:
        return jsonify({'error': 'ID no encontrado'}), 404

    data = descargas_activas[download_id]

    # Calcular posicion en cola
    posicion = 0
    with queue_lock:
        ids_cola = list(download_queue)
        if download_id in ids_cola:
            posicion = ids_cola.index(download_id) + 1

    if data['completado'] and data['resultado']:
        if data['resultado']['success']:
            return jsonify({
                'status': 'completado',
                'success': True,
                'archivo': os.path.basename(data['resultado']['archivo']),
                'nombre': data['resultado']['nombre']
            })
        else:
            return jsonify({
                'status': 'error',
                'success': False,
                'error': data['resultado']['error']
            })

    return jsonify({
        'status': data['status'],
        'progreso': data['progreso'],
        'posicion': posicion,
    })

@app.route('/download_file/<filename>')
def download_file(filename):
    filepath = DOWNLOAD_FOLDER / filename

    if not filepath.exists():
        return jsonify({'error': 'Archivo no encontrado'}), 404

    @after_this_request
    def eliminar_archivo(response):
        try:
            time.sleep(1)
            if filepath.exists():
                filepath.unlink()
        except:
            pass
        return response

    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
