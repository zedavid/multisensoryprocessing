import pyaudio
import sys
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

if len(sys.argv) < 2 or len(sys.argv) > 3:
    exit('Please provide one or two micrphones')
if len(sys.argv) >= 2:
    device_indexes = [int(sys.argv[1])]
    zmq_socket_1, zmq_server_addr_1 = create_zmq_server()
if len(sys.argv) == 3:
    device_indexes.index(int(sys.argv[2]))
    zmq_socket_2, zmq_server_addr_2 = create_zmq_server(s)

FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 48000
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
if len(device_names) > 1:
    mq.publish(
        exchange='sensors',
        routing_key='microphone.new_sensor.{}'.format(device_names[1]),
        body={'address': zmq_server_addr_2, 'file_type': 'audio'}
    )

session_name = datetime.datetime.now().isoformat().replace('.', '_').replace(':', '_') + '.'.join(device_names)

# Let's be on the safe side and recording this to the computer...
waveFile = wave.open('{}.wav'.format(session_name), 'wb')
waveFile.setnchannels(CHANNELS)
waveFile.setsampwidth(p.get_sample_size(FORMAT))
waveFile.setframerate(RATE)

def callback(in_data, frame_count, time_info, status):
    result = np.fromstring(in_data, dtype=np.uint16)
    result = np.reshape(result, (frame_count, 2))
    the_time = mq.get_shifted_time()
    zmq_socket_1.send(msgpack.packb((result[:, 0].tobytes(), the_time)))
    if len(device_names) > 1:
        zmq_socket_2.send(msgpack.packb((result[:, 1].tobytes(), the_time)))
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
    if len(device_names) > 1:
        zmq_socket_2.send(b'CLOSE')
        zmq_socket_2.close()
