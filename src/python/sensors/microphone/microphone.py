import pyaudio
import sys,os
import time
import msgpack
sys.path.append('../..')
import numpy as np
import re
from shared import create_zmq_server, MessageQueue
import sys
import datetime
from threading import Thread, Event
import wave
import yaml

# Settings
SETTINGS_FILE = '../../settings.yaml'
settings = yaml.safe_load(open(SETTINGS_FILE, 'r').read())

session_name = '{}.{}.{}'.format(settings['participants']['left']['name'].lower(),
                                    settings['participants']['right']['name'].lower(),
                                    settings['participants']['condition'])


log_path = os.path.join(settings['logging']['log_path'], session_name)

if not os.path.isdir(log_path):
    os.makedirs(log_path)

print(log_path)

if len(sys.argv) < 2 or len(sys.argv) > 3:
    exit('Please provide one microphone and the participant position')
else:
    device_indexes = [int(sys.argv[1])]
    position = sys.argv[2]
    zmq_socket_1, zmq_server_addr_1 = create_zmq_server()

FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 16000
CHUNK = 1440

mq = MessageQueue('microphone-sensor')
p = pyaudio.PyAudio()
device_names = []
for i in range(p.get_device_count()):
    device = p.get_device_info_by_index(i)
    print(i,device['name'])
    if i in device_indexes:
        device_names.append(device['name'])


mq.publish(
    exchange='sensors',
    routing_key='microphone.new_sensor.{}'.format(device_names[0]),
    body={'address': zmq_server_addr_1, 'file_type': 'audio'}
)

# Let's be on the safe side and recording this to the computer...
waveFile = wave.open(os.path.join(log_path,'{}.wav'.format(settings['participants'][position]['name'].lower())), 'wb')
waveFile.setnchannels(CHANNELS)
waveFile.setsampwidth(p.get_sample_size(FORMAT))
waveFile.setframerate(RATE)

def callback(in_data, frame_count, time_info, status):
    result = np.fromstring(in_data, dtype=np.uint16)
    result = np.reshape(result, (frame_count, 2))
    the_time = mq.get_shifted_time()
    zmq_socket_1.send(msgpack.packb((result[:, 0].tobytes(), the_time)))
    waveFile.writeframes(in_data)
    return None, pyaudio.paContinue


stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=CHUNK,
    stream_callback=callback
)
try:
    input('[*] Serving at {}. To exit press enter'.format(','.join(device_names)))
finally:
    waveFile.close()
    stream.stop_stream()
    stream.close()
    zmq_socket_1.send(b'CLOSE')
    zmq_socket_1.close()
