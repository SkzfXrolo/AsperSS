"""
Registra los slash commands de ASPERS en Discord.
Ejecutar UNA VEZ desde tu PC (no desde Render).

Uso:
  pip install requests
  python register_discord_commands.py
"""
import os
import sys
import requests

BOT_TOKEN = input("Pega tu DISCORD_TOKEN (bot token): ").strip()
APP_ID    = input("Pega tu DISCORD_APP_ID (Application ID): ").strip()
GUILD_ID  = input("Pega tu DISCORD_GUILD (Guild ID, Enter para comandos globales): ").strip()

COMMANDS = [
    {
        'name': 'scan',
        'description': 'Muestra el último scan de un jugador',
        'options': [{'name': 'jugador', 'description': 'Nombre de máquina o username', 'type': 3, 'required': True}],
    },
    {
        'name': 'stats',
        'description': 'Estadísticas globales del panel',
        'options': [],
    },
    {
        'name': 'veredicto',
        'description': 'Cambia el veredicto de un scan (staff)',
        'options': [
            {'name': 'scan_id',   'description': 'ID del scan',            'type': 4, 'required': True},
            {'name': 'veredicto', 'description': 'hack | clean | pending', 'type': 3, 'required': True},
            {'name': 'razon',     'description': 'Razón del veredicto',    'type': 3, 'required': True},
        ],
    },
    {
        'name': 'ss',
        'description': 'Screen Share — crea token para el jugador (staff)',
        'options': [{'name': 'jugador', 'description': '@mention del jugador', 'type': 6, 'required': True}],
    },
]

API = 'https://discord.com/api/v10'
headers = {'Authorization': f'Bot {BOT_TOKEN}', 'Content-Type': 'application/json'}

url = (f'{API}/applications/{APP_ID}/guilds/{GUILD_ID}/commands'
       if GUILD_ID else f'{API}/applications/{APP_ID}/commands')

print(f'\nRegistrando {len(COMMANDS)} comandos...')
r = requests.put(url, headers=headers, json=COMMANDS)

if r.ok:
    cmds = r.json()
    print(f'✅ {len(cmds)} comandos registrados:')
    for c in cmds:
        print(f"   /{c['name']}")
else:
    print(f'❌ Error {r.status_code}: {r.text[:300]}')
    sys.exit(1)

print('\nListo. Los comandos tardan hasta 1 hora en aparecer si son globales.')
print('Con Guild ID aparecen al instante.')
