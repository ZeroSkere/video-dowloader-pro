import sqlite3
import os
import shutil
from pathlib import Path

def extraer_cookies_brave():
    # Ruta de cookies de Brave
    brave_path = os.path.expanduser('~') + r'\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\Network\Cookies'
    
    if not os.path.exists(brave_path):
        print("❌ No se encontró Brave con datos")
        print("Buscando en ubicación alternativa...")
        brave_path = os.path.expanduser('~') + r'\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\Cookies'
        
    if not os.path.exists(brave_path):
        print("❌ No se encontró la base de datos de cookies de Brave")
        return False
    
    # Copiar archivo (está en uso)
    temp_path = 'temp_brave_cookies.db'
    try:
        shutil.copy2(brave_path, temp_path)
    except:
        print("❌ Asegúrate de cerrar Brave completamente")
        return False
    
    # Conectar a la base de datos
    conn = sqlite3.connect(temp_path)
    cursor = conn.cursor()
    
    # Extraer cookies de YouTube
    cursor.execute("""
        SELECT host_key, path, is_secure, expires_utc, name, value 
        FROM cookies 
        WHERE host_key LIKE '%youtube.com%' 
        OR host_key LIKE '%google.com%'
    """)
    
    cookies_data = cursor.fetchall()
    
    if not cookies_data:
        print("❌ No se encontraron cookies de YouTube")
        print("Asegúrate de haber iniciado sesión en YouTube en Brave")
        conn.close()
        os.remove(temp_path)
        return False
    
    # Escribir archivo cookies.txt en formato Netscape
    with open('cookies.txt', 'w', encoding='utf-8') as f:
        f.write('# Netscape HTTP Cookie File\n')
        f.write('# https://curl.se/rfc/cookie_spec.html\n\n')
        for row in cookies_data:
            host, path, secure, expires, name, value = row
            domain_flag = 'TRUE' if host.startswith('.') else 'FALSE'
            secure_flag = 'TRUE' if secure else 'FALSE'
            if isinstance(expires, int) and expires > 0:
                if expires > 4000000000000:
                    expires = int((expires - 11644473600000000) / 1000000)
                elif expires > 100000000000:
                    expires = int(expires / 1000000)
            else:
                expires = 0
            f.write(f"{host}\t{domain_flag}\t{path}\t{secure_flag}\t{expires}\t{name}\t{value}\n")
    
    conn.close()
    os.remove(temp_path)
    
    print(f"✅ cookies.txt creado con {len(cookies_data)} cookies")
    return True

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    print("[INFO] Extrayendo cookies de Brave...")
    print("[INFO] Asegurate de haber cerrado Brave completamente")
    input("Presiona Enter para continuar...")
    
    if extraer_cookies_brave():
        print("[OK] Listo! cookies.txt generado")
    else:
        print("[ERROR] No se pudieron extraer cookies")