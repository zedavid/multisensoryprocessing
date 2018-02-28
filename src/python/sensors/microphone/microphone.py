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
import argparse

# Settings
SETTINGS_FILE = '../../settings.yaml'
settings = yaml.safe_load(open(SETTINGS_FILE, 'r').read())

session_name = '{}.{}.{}'.format(settings['participants']['left']['name'].lower(),
                                    settings['participants']['right']['name'].lower(),
                                    settings['participants']['condition'])


log_path = os.path.join(settings['logging']['log_path'], session_name)

if not os.path.isdir(log_path):
    os.makedirs(log_path)

parser = argparse.ArgumentParser(description='Collects data from microphones')
parser.add_argument('--device', '-d', type=int,help='device used to capture',required=True)
parser.add_argument('--channels','-c',type=int,nargs='+',help='channels that are going to be saved')
parser.add_argument('--num_channels','-n',type=int,help='number of channels to be recorded',default=2)

args = parser.parse_args()


device_indexes = [args.device]
if len(args.channels) > 2:
    exit('provide only two channels')

zmq_socket_1, zmq_server_addr_1 = create_zmq_server()
zmq_socket_2, zmq_server_addr_2 = create_zmq_server()

FORMAT = pyaudio.paInt16
CHANNELS = args.num_channels
RATE = 16000
CHUNK = 1440

for ch in args.channels:
    if ch > CHANNELS:
        exit('device does not have channel {}'.format(ch))

mq = MessageQueue('microphone-sensor')
p = pyaudio.PyAudio()
device_names = []
for i in range(p.get_device_count()):
    device = p.get_device_info_by_index(i)
    print(i,device['name'])
    if i in device_indexes:
        device_names.append(device['name'])

if len(device_names) < 1:
    exit('No microphone was detected')

mq.publish(
    exchange='sensors',
    routing_key='microphone.new_sensor.left',
    body={'address': zmq_server_addr_1, 'file_type': 'audio'}
)

mq.publish(
    exchange='sensors',
    routing_key='microphone.new_sensor.right',
    body={'address': zmq_server_addr_2, 'file_type': 'audio'}
)

# Let's be on the safe side and recording this to the computer...
waveFile = wave.open(os.path.join(log_path,'two_channels.wav'), 'wb')
waveFile.setnchannels(CHANNELS)
waveFile.setsampwidth(p.get_sample_size(FORMAT))
waveFile.setframerate(RATE)

#waveFile2 = wave.open(os.path.join(log_path,'{}.wav'.format(settings['participants']['left']['name'].lower())), 'wb')
#waveFile2.setnchannels(CHANNELS)
#waveFile2.setsampwidth(p.get_sample_size(FORMAT))
#waveFile2.setframerate(RATE)


def callback(in_data, frame_count, time_info, status):
    result = np.fromstring(in_data, dtype=np.uint16)
    result = np.reshape(result, (frame_count, CHANNELS))
    the_time = mq.get_shifted_time()
    # assuming the channels that we want to record
    zmq_socket_1.send(msgpack.packb((result[:, args.channels[0]].tobytes(), the_time)))
    zmq_socket_2.send(msgpack.packb((result[:, args.channels[1]].tobytes(), the_time)))
    waveFile.writeframes(in_data)
    return None, pyaudio.paContinue



stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input_device_index=device_indexes[0],
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
    zmq_socket_2.send(b'CLOSE')
    zmq_socket_2.close()
