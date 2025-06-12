from flask import Flask, jsonify, render_template, send_from_directory
import paho.mqtt.client as mqtt
import requests
import logging
import time
import os
from dotenv import load_dotenv
from flask_cors import CORS

# Configurações iniciais
load_dotenv()
app = Flask(__name__)
CORS(app)  # Habilita CORS para todas as rotas

# Variáveis globais
THINGSPEAK_CHANNEL_ID = os.getenv('THINGSPEAK_CHANNEL_ID')
THINGSPEAK_READ_KEY = os.getenv('THINGSPEAK_READ_KEY')
MQTT_BROKER = os.getenv('MQTT_BROKER', 'test.mosquitto.org')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
pump_state = False
mqtt_connected = False

# Configuração de logging
logging.basicConfig(level=logging.INFO)

# Callbacks MQTT
def on_mqtt_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        client.subscribe("pump/status")
        logging.info("Conectado ao MQTT Broker!")
    else:
        logging.error(f"Falha na conexão MQTT. Código: {rc}")

def on_mqtt_message(client, userdata, msg):
    global pump_state
    payload = msg.payload.decode()
    if msg.topic == "pump/status":
        pump_state = (payload == "ON")
        logging.info(f"Estado da bomba atualizado: {payload}")

def on_mqtt_disconnect(client, userdata, rc):
    global mqtt_connected
    mqtt_connected = False
    logging.warning("MQTT desconectado. Tentando reconectar...")
    time.sleep(5)
    client.reconnect()

# Conexão MQTT
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_message = on_mqtt_message
mqtt_client.on_disconnect = on_mqtt_disconnect
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

# Rotas
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/api/water-data')
def get_water_data():
    try:
        url = f'https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL_ID}/feeds.json'
        params = {'api_key': THINGSPEAK_READ_KEY, 'results': 24}
        response = requests.get(url, params=params)
        data = response.json()
        feeds = data.get('feeds', [])
        values = [float(feed['field1']) for feed in feeds if 'field1' in feed and feed['field1']]
        timestamps = [feed['created_at'] for feed in feeds if 'field1' in feed and feed['field1']]
        return jsonify({'values': values, 'timestamps': timestamps})
    except Exception as e:
        logging.error(f"Erro ao obter dados: {e}")
        return jsonify({'values': [], 'timestamps': []})

@app.route('/api/pump/status')
def get_pump_status():
    return jsonify({'status': 'ON' if pump_state else 'OFF'})

@app.route('/api/pump/control/<state>', methods=['POST'])
def control_pump(state):
    if state.upper() in ['ON', 'OFF']:
        mqtt_client.publish("equibigas2420q", "1" if state.upper() == "ON" else "0")
        return jsonify({'success': True})
    return jsonify({'success': False}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)