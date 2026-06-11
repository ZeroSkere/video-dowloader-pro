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

# Headers HTTP para evitar bloqueos
COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-us,en;q=0.5',
}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu-clave-secreta'
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Crear carpetas necesarias
DOWNLOAD_FOLDER = Path(__file__).parent / 'downloads'
DOWNLOAD_FOLDER.mkdir(exist_ok=True)

TEMP_FOLDER = Path(__file__).parent / 'temp'
TEMP_FOLDER.mkdir(exist_ok=True)

descargas_activas = {}

def verificar_ffmpeg():
    """Verifica si ffmpeg está disponible en el servidor"""
    import subprocess
    import platform
    
    # En Render, no está disponible
    if 'RENDER' in os.environ:
        return False
    
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True)
        return True
    except:
        return False

def obtener_info_video(url):
    """Obtiene información del video con manejo de errores mejorado"""
    
    # Detectar plataformas con DRM
    url_lower = url.lower()
    
    if 'spotify.com' in url_lower:
        return {
            'success': False,
            'error': '❌ Spotify usa protección DRM y NO se puede descargar.\n\n✅ Alternativas:\n• Busca la canción en YouTube y usa ese enlace\n• Usa la aplicación oficial de Spotify para descargar (solo Premium)'
        }
    
    if 'netflix.com' in url_lower:
        return {
            'success': False,
            'error': '❌ Netflix usa protección DRM y NO se puede descargar.\n\n✅ Usa la aplicación oficial de Netflix para descargas offline.'
        }
    
    if 'primevideo.com' in url_lower or 'amazon.com' in url_lower and 'video' in url_lower:
        return {
            'success': False,
            'error': '❌ Amazon Prime Video usa protección DRM y NO se puede descargar.\n\n✅ Usa la aplicación oficial de Prime Video para descargas offline.'
        }
    
    if 'disneyplus.com' in url_lower:
        return {
            'success': False,
            'error': '❌ Disney+ usa protección DRM y NO se puede descargar.\n\n✅ Usa la aplicación oficial de Disney+ para descargas offline.'
        }
    
    if 'hbomax.com' in url_lower or 'max.com' in url_lower:
        return {
            'success': False,
            'error': '❌ HBO Max usa protección DRM y NO se puede descargar.'
        }
    
    # Continuar con la descarga normal para plataformas compatibles
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'http_headers': COMMON_HEADERS,
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'android'],
                'player_skip': ['webpage'],
            }
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Obtener formatos de video
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
                'titulo': info.get('title', 'Sin título'),
                'duracion': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'formatos_video': formatos_video[:10],
                'plataforma': 'youtube' if 'youtube.com' in url or 'youtu.be' in url else 'compatible'
            }
    except Exception as e:
        error_msg = str(e)
        if 'DRM' in error_msg:
            return {
                'success': False,
                'error': '❌ Este sitio usa protección DRM y no permite descargas.\n\n✅ Prueba con YouTube, Vimeo, Dailymotion o SoundCloud.'
            }
        return {
            'success': False,
            'error': f'Error: {error_msg}'
        }

def descargar_video(url, formato_id, es_audio=False, callback_id=None):
    """Descarga el video o audio"""
    nombre_archivo = str(uuid.uuid4())
    ffmpeg_disponible = verificar_ffmpeg()
    
    base_opts = {
        'outtmpl': str(DOWNLOAD_FOLDER / f'{nombre_archivo}.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'http_headers': COMMON_HEADERS,
        'progress_hooks': [lambda d: hook_progreso(d, callback_id)],
    }

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
            
            # Si es audio y no se convirtió a MP3, cambiar extensión si es necesario
            if es_audio and not ffmpeg_disponible:
                # Renombrar a .mp3 aunque sea otro formato
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
    """Callback para progreso"""
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
    
    def descarga_background():
        resultado = descargar_video(url, formato_id, es_audio, download_id)
        descargas_activas[download_id]['resultado'] = resultado
        descargas_activas[download_id]['completado'] = True
    
    descargas_activas[download_id] = {
        'progreso': 0,
        'completado': False,
        'resultado': None
    }
    
    thread = threading.Thread(target=descarga_background)
    thread.start()
    
    return jsonify({'download_id': download_id})

@app.route('/progress/<download_id>')
def progress(download_id):
    if download_id not in descargas_activas:
        return jsonify({'error': 'ID no encontrado'}), 404
    
    data = descargas_activas[download_id]
    
    if data['completado'] and data['resultado']:
        if data['resultado']['success']:
            return jsonify({
                'completado': True,
                'success': True,
                'archivo': os.path.basename(data['resultado']['archivo']),
                'nombre': data['resultado']['nombre']
            })
        else:
            return jsonify({
                'completado': True,
                'success': False,
                'error': data['resultado']['error']
            })
    
    return jsonify({
        'completado': False,
        'progreso': data['progreso']
    })

@app.route('/download_file/<filename>')
def download_file(filename):
    filepath = DOWNLOAD_FOLDER / filename
    
    if not filepath.exists():
        return jsonify({'error': 'Archivo no encontrado'}), 404
    
    @after_this_request
    def eliminar_archivo(response):
        try:
            time.sleep(1)  # Esperar 1 segundo antes de eliminar
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
    # Render usa el puerto asignado por la variable de entorno
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)