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
    
    # Escribir archivo cookies.txt
    with open('cookies.txt', 'w') as f:
        for row in cookies_data:
            host, path, secure, expires, name, value = row
            secure_flag = 'TRUE' if secure else 'FALSE'
            # Convertir timestamp
            if expires > 0 and expires < 4000000000000:
                expires = int(expires / 1000000)
            elif expires > 4000000000000:
                expires = int((expires - 116444736000000000) / 10000000)
            else:
                expires = 0
            
            f.write(f"{host}\t{secure_flag}\t{path}\t{secure_flag}\t{expires}\t{name}\t{value}\n")
    
    conn.close()
    os.remove(temp_path)
    
    print(f"✅ cookies.txt creado con {len(cookies_data)} cookies")
    return True

if __name__ == "__main__":
    print("🔍 Extrayendo cookies de Brave...")
    print("⚠️ Asegúrate de haber cerrado Brave completamente")
    input("Presiona Enter para continuar...")
    
    if extraer_cookies_brave():
        print("\n✅ ¡Listo! Ahora ejecuta test_cookies.py")
    else:
        print("\n❌ Error. Usa la Opción 2 (extensión manual)")