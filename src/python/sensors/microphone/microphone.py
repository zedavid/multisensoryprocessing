import datetime,re,time
import wave, msgpack

import pyaudio, yaml
import os, argparse, sys
import numpy as np

from farmi import Publisher
sys.path.append('../..')
from shared import create_zmq_server

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 2000

SETTINGS_FILE = os.path.join('../../settings.yaml')

settings = yaml.safe_load(open(SETTINGS_FILE, 'r').read())

mission_name = settings['mission']['file'].split(os.sep)[-1].split('.')[0]
session_name = f"{mission_name}.{settings['speaker']['id']}.{settings['condition']}"

log_path = os.path.join(settings['logging']['log_path'], session_name)

if not os.path.isdir(log_path):
    os.makedirs(log_path)

mic_pub = Publisher('microphone-sensor',
                    local_save=log_path,
                    directory_service_address=f"tcp://{settings['FARMI_DIRECTORY_SERVICE_IP']}:5555")

parser = argparse.ArgumentParser(description='Collects data from microphones')
parser.add_argument('--device', '-d', type=int,help='device used to capture',required=True)
parser.add_argument('--channels','-c',type=int,nargs='+',help='channels that are going to be saved',required=True)
parser.add_argument('--num_channels','-n',type=int,help='number of channels to be recorded',default=2)
args = parser.parse_args()

device_indexes = [args.device]
if len(args.channels) > 2:
    exit('provide only two channels')

FORMAT = pyaudio.paInt16
CHANNELS = args.num_channels
RATE = 16000
CHUNK = 1024
BUF_MAX_SIZE = CHUNK * 10

p = pyaudio.PyAudio()
device_names = []
for i in range(p.get_device_count()):
    device = p.get_device_info_by_index(i)
    print(i,device['name'])
    if i in device_indexes:
        device_names.append(device['name'])

zmq_socket, zmq_server_addr = create_zmq_server.create_zmq_server()

if len(device_names) < 1:
    exit('No microphone was detected')


session_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + '_' + re.sub('\s+', '_', '_'.join(device_names))
audio_file_name = os.path.join(log_path,'{}.wav'.format(session_name))

mic_pub.send(({'address': zmq_server_addr, 'file_type': 'audio', 'file_name':audio_file_name, 'chunk': CHUNK, 'buf_max_size': BUF_MAX_SIZE, 'channels':CHANNELS, 'rate':RATE},'microphone.{}'.format(settings['speaker']['id'])))

# Let's be on the safe side and recording this to the computer...
waveFile = wave.open(audio_file_name, 'wb')
waveFile.setnchannels(CHANNELS)
waveFile.setsampwidth(p.get_sample_size(FORMAT))
waveFile.setframerate(RATE)

def callback(in_data, frame_count, time_info, status):
    result = np.fromstring(in_data, dtype=np.uint16)
    result = np.reshape(result, (frame_count, CHANNELS))
#    the_time = mq.get_shifted_time()
    zmq_socket.send(msgpack.packb((result[:, args.channels[0]].tobytes(),time.time())))
    #zmq_socket.send(result[:, args.channels[0]].tobytes())
    waveFile.writeframes(in_data)
    return None, pyaudio.paContinue

print(f'test file in {audio_file_name}')

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
    input('[*] Serving at {}. To exit press enter'.format(zmq_server_addr,))
finally:
    waveFile.close()
    stream.stop_stream()
    stream.close()
    zmq_socket.send(b'CLOSE')
    zmq_socket.close()
