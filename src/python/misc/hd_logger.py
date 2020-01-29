import sys,argparse
import zmq
sys.path.append('..')
from farmi import Subscriber
import datetime
import yaml
import os
from threading import Thread
import queue
import json
import time
import shutil

parser = argparse.ArgumentParser(description='Logs data to folder in a local hard drive')
parser.add_argument('--settings_file','-s',type=str,help='settings file use for the experiment')
parser.add_argument('--listening_routing_key','-l',type=str,help='routing key that the logger is going to be listening',default='*.new_sensor.*')

args = parser.parse_args()

settings = yaml.safe_load(open(args.settings_file, 'r').read())

if 'orca' in settings['speaker']['id'].split('_'):
    # setting for orca experiments
    mission_name = settings['mission']['file'].split(os.sep)[-1].split('.')[0]
    session_name = '{}.{}.{}'.format(mission_name, settings['speaker']['id'], settings['condition'])
else:
    # setting for language café experiment
    session_name = '{}.{}.{}'.format(settings['participants']['left']['id'].lower(),
                                        settings['participants']['right']['id'].lower(),
                                        settings['participants']['condition'])

log_path = os.path.join(settings['logging']['log_path'], session_name)

if not os.path.isdir(log_path):
    os.makedirs(log_path)

shutil.copy(args.settings_file, os.path.join(log_path, 'settings.yaml'))
global_runner = True
running = {}
sockets = []

def callback(subtopic, time_given, data):

    global running

    routing_key = data[1]
    body = data[0]

    a = 0
    go_on = True
    q = queue.Queue()

    while go_on:
        try:
            os.mkdir(os.path.join(log_path, '{}-{}'.format(routing_key, a)))
            go_on = False
        except FileExistsError:
            a += 1

    log_file = os.path.join(
        log_path,
        '{}-{}'.format(routing_key, a), 'data.{}'.format(body.get('file_type', 'unknown'))
    )
    running[log_file] = True

    print('[{}] streamer connected'.format(log_file))
    with open(os.path.join(log_path, '{}-{}'.format(routing_key, a), 'info.txt'), 'w') as f:
        f.write(json.dumps(body))

    def run(log_file):
        global global_runner, running

        context = zmq.Context()
        s = context.socket(zmq.SUB)
        s.setsockopt_string( zmq.SUBSCRIBE, '' )
        # s.RCVTIMEO = 30000
        s.connect(body['address'])
        sockets.append(s)
        t = time.time()

        d = bytes()
        while running[log_file] and global_runner:
            data = s.recv()
            if data == b'CLOSE':
                print('close received')
                running[log_file] = False
                break
            d += data
            if time.time() - t > 5:
                q.put(d)
                d = bytes()

        global_runner = True
        if d:
            q.put(d)

        s.close()
        print('[{}] streamer closed'.format(log_file))


    def storage_writer(log_file):
        global global_runner, running
        with open(log_file, 'ab') as f:
            while global_runner or q.qsize() != 0:
                data = q.get()
                f.write(data)
                print('{} writes left to do..', q.qsize())
        print('writer closed'.format(log_file))

    _thread = Thread(target = run, args=(log_file, ))
    _thread.deamon = True
    _thread.start()

    thread = Thread(target = storage_writer, args=(log_file, ))
    thread.deamon = True
    thread.start()

logger_listner = Subscriber(directory_service_address=f"tcp://{settings['FARMI_DIRECTORY_SERVICE_IP']}:5555")
logger_listner.subscribe_to('microphone-sensor', callback)
logger_listner.subscribe_to('video-sensor',callback)
logger_listner.listen()
#mq = MessageQueue('logger')
#mq.bind_queue(
#    exchange='sensors', routing_key=listen_to_routing_key, callback=callback
#)

#resend_new_sensor_messages.resend_new_sensor_messages()
print('[*] Waiting for messages. To exit press CTRL-C')