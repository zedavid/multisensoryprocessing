import time
import msgpack
import cv2
import sys,os,argparse
import scipy.ndimage
import datetime
sys.path.append('../..')
from farmi import Publisher
from shared import create_zmq_server, MessageQueue
zmq_socket, zmq_server_addr = create_zmq_server()
import yaml

parser = argparse.ArgumentParser(description='Video recording script')
parser.add_argument('--setting_file','-s',type=str,help='settings file use for the experiment',required=True)
parser.add_argument('--camera_id','-c',type=int,help='camera identifier',required=True)

args = parser.parse_args()

settings = yaml.safe_load(open(args.setting_file, 'r').read())

mission_name = settings['mission']['file'].split(os.sep)[-1].split('.')[0]
session_name = '{}.{}.{}'.format(mission_name, settings['speaker']['id'],settings['condition'])

log_path = os.path.join(settings['logging']['log_path'], session_name)

if not os.path.isdir(log_path):
    os.makedirs(log_path)

pub = Publisher('video-sensor',local_save=log_path,directory_service_address=f"tcp://{settings['FARMI_DIRECTORY_SERVICE_IP']}:5555")

log_path = os.path.join(settings['logging']['log_path'], session_name)

if not os.path.isdir(log_path):
    os.makedirs(log_path)

fourcc = cv2.VideoWriter_fourcc(*'MP4V')

camera = cv2.VideoCapture(args.camera_id)
width = camera.get(cv2.CAP_PROP_FRAME_WIDTH)   # float
height = camera.get(cv2.CAP_PROP_FRAME_HEIGHT) # float
fps = camera.get(cv2.CAP_PROP_FPS)

if width != 640.0:
    width = 640.0
    camera.set(cv2.CAP_PROP_FRAME_WIDTH,width)


if height != 480.0:
    height = 480.0
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT,height)

if fps != 30.0:
    fps = 30.0
    camera.set(cv2.CAP_PROP_FPS,fps)

session_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + '_' + str(args.camera_id)

non_sync_video_filename = os.path.join(log_path,'{}.mp4'.format(session_name))

out = cv2.VideoWriter(non_sync_video_filename, fourcc, 30.0, (int(width), int(height)))


pub.send(({'address': zmq_server_addr,
        'file_type': 'cv-video',
        'img_size': {
            'width': width / 2,
            'height': height / 2,
            'channels': 3,
            'fps': fps,
        },
        'filename':non_sync_video_filename
    },'video.{}'.format(settings['speaker']['id'])))
print('[*] Serving at {}. To exit press CTRL+C.'.format(zmq_server_addr))
try:
    while True:
        _, frame = camera.read()
        out.write(frame)
        zmq_socket.send(msgpack.packb((scipy.ndimage.zoom(frame, (0.5, 0.5, 1), order=0).flatten().tobytes(), time.time())))

except KeyboardInterrupt:
    zmq_socket.send(b'CLOSE')
    zmq_socket.close()
