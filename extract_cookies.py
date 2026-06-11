"""Extract YouTube cookies from Brave/Chrome without needing admin.
Works by copying the cookie database (if browser is closed) or using Volume Shadow Copy.
"""
import sqlite3
import os
import shutil
import tempfile
from pathlib import Path

BRAVE_COOKIES = [
    os.path.expanduser('~') + r'\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\Network\Cookies',
    os.path.expanduser('~') + r'\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\Cookies',
]

def try_copy_db(paths):
    for p in paths:
        if os.path.exists(p):
            try:
                tmp = tempfile.mktemp(suffix='.db')
                shutil.copy2(p, tmp)
                return tmp
            except:
                continue
    return None

def extract(tmp_db):
    conn = sqlite3.connect(tmp_db)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT host_key, path, is_secure, expires_utc, name, value
        FROM cookies
        WHERE host_key LIKE '%youtube.com%'
           OR host_key LIKE '%google.com%'
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def to_netscape(rows, output):
    with open(output, 'w', encoding='utf-8') as f:
        f.write('# Netscape HTTP Cookie File\n')
        f.write('# https://curl.se/rfc/cookie_spec.html\n')
        f.write('# This is a generated file\n\n')
        for host, path, secure, expires, name, value in rows:
            # domain_specified: TRUE si el dominio empieza con '.', FALSE si no
            domain_specified = 'TRUE' if host.startswith('.') else 'FALSE'
            secure_flag = 'TRUE' if secure else 'FALSE'
            if isinstance(expires, int) and expires > 0:
                if expires > 4000000000000:
                    expires = int((expires - 11644473600000000) / 1000000)
                elif expires > 100000000000:
                    expires = int(expires / 1000000)
            else:
                expires = 0
            f.write(f"{host}\t{domain_specified}\t{path}\t{secure_flag}\t{expires}\t{name}\t{value}\n")

def main():
    output = Path(__file__).parent / 'cookies.txt'

    if not os.path.exists(BRAVE_COOKIES[0]) and not os.path.exists(BRAVE_COOKIES[1]):
        print("No se encontraron cookies de Brave. Cerraste Brave completamente?")
        return False

    tmp_db = try_copy_db(BRAVE_COOKIES)
    if not tmp_db:
        print("No se pudo copiar la base de datos. Asegurate de cerrar Brave.")
        return False

    rows = extract(tmp_db)
    os.unlink(tmp_db)

    if not rows:
        print("No se encontraron cookies de YouTube en Brave.")
        return False

    to_netscape(rows, output)
    print(f"Extraidas {len(rows)} cookies a {output}")
    return True

if __name__ == '__main__':
    main()
