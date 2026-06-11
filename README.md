# Video Downloader Pro

Aplicación web para descargar videos y música desde YouTube y más de 1000 sitios. Construida con Python, Flask y yt-dlp. Desplegada en Render.

## Caracteristicas

- Descarga desde YouTube, Vimeo, Dailymotion, TikTok y mas
- Conversion a MP3 (extrae audio de cualquier video)
- Multiples calidades: desde 144p hasta 4K/8K
- Barra de progreso en tiempo real
- Interfaz responsiva (movil y desktop)
- Deteccion automatica de formatos disponibles
- Limpieza automatica de archivos temporales

## Requisitos

- Python 3.8+
- pip

## Instalacion local

```bash
git clone https://github.com/ZeroSkere/video-dowloader-pro.git
cd video-downloader-pro
pip install -r requirement.txt
python app.py
```

Abrir `http://localhost:5000` en el navegador.

## Despliegue en Render

1. Conecta el repositorio en Render
2. Selecciona "Web Service"
3. Configuracion:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirement.txt`
   - **Start Command**: `gunicorn app:app`
4. Listo. Render asigna automaticamente el puerto.

## Estructura

```
├── app.py              # Aplicacion Flask
├── templates/
│   └── index.html      # Frontend
├── downloads/          # Archivos descargados (temporal)
├── temp/               # Archivos temporales
├── requirement.txt     # Dependencias
└── render.yaml         # Config de Render
```

## Notas

- YouTube puede requerir cookies frescas en algunos casos. Si falla, genera cookies con: `yt-dlp --cookies-from-browser brave --cookies cookies.txt`
- Sin cookies la app funciona correctamente gracias a headers HTTP y extractor_args.
- FFmpeg es opcional (mejora calidad de audio MP3).
