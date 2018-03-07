import zmq
import pika
import time
import msgpack
import cv2
import sys,os
import zmq
import numpy as np
import subprocess
import scipy.ndimage
import datetime
sys.path.append('../..')
from shared import create_zmq_server, MessageQueue
zmq_socket, zmq_server_addr = create_zmq_server()
import yaml

# Settings
SETTINGS_FILE = '../../settings.yaml'
settings = yaml.safe_load(open(SETTINGS_FILE, 'r').read())

session_name = '{}.{}.{}'.format(settings['participants']['left']['id'].lower(),
                                    settings['participants']['right']['id'].lower(),
                                    settings['participants']['condition'])


log_path = os.path.join(settings['logging']['log_path'], session_name)

if not os.path.isdir(log_path):
    os.makedirs(log_path)

if len(sys.argv) != 3:
    exit('error. python video_cv.py [position] [camera]')

position = sys.argv[1]
camera_id = int(sys.argv[2])

fourcc = cv2.VideoWriter_fourcc(*'MP4V')

camera = cv2.VideoCapture(camera_id)
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

print(width,height,fps)

print(os.path.join(log_path,'{}.mp4'.format(settings['participants'][position]['id'].lower())))

out = cv2.VideoWriter(os.path.join(log_path,'{}.mp4'.format(settings['participants'][position]['id'].lower())), fourcc, 30.0, (int(width), int(height)))


mq = MessageQueue('video-webcam-sensor')
mq.publish(
    exchange='sensors',
    routing_key='video.new_sensor.{}'.format(settings['participants'][position]['id'].lower()),
    body={
        'address': zmq_server_addr,
        'file_type': 'cv-video',
        'img_size': {
            'width': width / 2,
            'height': height / 2,
            'channels': 3,
            'fps': fps,
        }
    }
)
print('[*] Serving at {}. To exit press CTRL+C.'.format(zmq_server_addr))
try:
    while True:
        _, frame = camera.read()
        out.write(frame)
        zmq_socket.send(msgpack.packb((scipy.ndimage.zoom(frame, (0.5, 0.5, 1), order=0).flatten().tobytes(), time.time())))

except KeyboardInterrupt:
    mq.disconnect('video.disconnected_sensor.{}'.format(settings['participants'][position]['id']))
    zmq_socket.send(b'CLOSE')
    zmq_socket.close()
