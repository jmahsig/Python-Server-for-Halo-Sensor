# halo_server.py
import socket
import threading
import sqlite3
from datetime import datetime

DB_NAME = 'halo_heartbeats.db'
TABLE_NAME = 'heartbeats'

# List of sensor fields expected in the message
SENSOR_FIELDS = [
    'C', 'F', 'RH', 'Lux', 'TVOC', 'CO2cal', 'PM1', 'PM2.5', 'PM10', 'NH3', 'NO2', 'CO',
    'AccX', 'AccY', 'AccZ', 'Move', 'P-Hg', 'P-hPa', 'AQI', 'NO2AQI', 'COAQI', 'PM10AQI',
    'PM25AQI', 'INP', 'CO2eq', 'panic', 'Motion', 'Noise', 'HGMic', 'LGMic', 'Aud1',
    'Gun', 'KW1', 'KW2', 'KW3', 'HI', 'HIco2', 'HIhum', 'HIpm1', 'HIpm2.5', 'HIpm10',
    'HItvoc', 'HIno2'
]


def load_approved_macs(filename='approved_macs.txt'):
    try:
        with open(filename, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        print(f"Warning: {filename} not found. No MACs approved.")
        return set()

APPROVED_MACS = load_approved_macs()

# Create database and table if not exists
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    columns = ', '.join([f'"{field}" TEXT' for field in SENSOR_FIELDS])
    c.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            mac TEXT,
            name TEXT,
            {columns}
        )
    ''')
    conn.commit()
    conn.close()

# Parse message from sensor
def parse_message(msg):
    parts = msg.strip().split(',')
    if len(parts) < 3:
        return None
    mac = parts[0]
    name = parts[1]
    sensor_data = {}
    for item in parts[2:]:
        if '=' in item:
            key, value = item.split('=', 1)
            sensor_data[key] = value
    return mac, name, sensor_data

# Save heartbeat to database
def save_heartbeat(mac, name, sensor_data):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    values = [timestamp, mac, name]
    for field in SENSOR_FIELDS:
        values.append(sensor_data.get(field, None))
    placeholders = ', '.join(['?'] * (3 + len(SENSOR_FIELDS)))
    quoted_fields = ', '.join([f'"{field}"' for field in SENSOR_FIELDS])
    c.execute(f"INSERT INTO {TABLE_NAME} (timestamp, mac, name, {quoted_fields}) VALUES ({placeholders})", values)
    conn.commit()
    conn.close()

# Handle each client connection
def handle_client(conn, addr):
    print(f"Connected by {addr}")
    with conn:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            msg = data.decode('utf-8')
            print(f"Received: {msg}")
            parsed = parse_message(msg)
            if parsed:
                mac, name, sensor_data = parsed
                if mac in APPROVED_MACS:
                    save_heartbeat(mac, name, sensor_data)
                    print(f"Logged heartbeat from {mac} ({name})")
                else:
                    print(f"Rejected heartbeat from unapproved MAC: {mac}")
            else:
                print("Invalid message format.")

# Main server loop
def start_server(host='0.0.0.0', port=9000):
    init_db()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen()
        print(f"Server listening on {host}:{port}")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == '__main__':
    start_server()
