import zmq
import pika
import json
import time
import msgpack
import re
import sys
sys.path.append('..')
from shared import MessageQueue
import yaml
import os
import json
import msgpack
from collections import defaultdict
import datetime

# Settings
SETTINGS_FILE = '../settings.yaml'
settings = yaml.safe_load(open(SETTINGS_FILE, 'r').read())

session_name = '{}.{}.{}'.format(settings['participants']['left']['id'].lower(),
                                    settings['participants']['right']['id'].lower(),
                                    settings['participants']['condition'])


log_path = os.path.join(settings['logging']['log_path'], session_name)

if not os.path.isdir(log_path):
    os.makedirs(log_path)

try:
    os.remove(os.path.join(log_path,'events.log'))
except OSError:
    pass

# Procees input data
def callback(ch, method, properties, body):
    # participant = routing_key.rsplit('.', 1)[1]
    body_dict = json.loads(body.decode())
    if 'timestamps' not in body_dict:
        print(body_dict)
        sys.exit()
    for ts in body_dict['timestamps']:
        print(ts)
        time_stamp = datetime.datetime.fromtimestamp(float(ts['departed'])).strftime('%Y-%m-%d %H:%M:%S')
    path = os.path.join(log_path, 'events.log')
    with open(path, 'a') as f:
        f.write('{}:\t{}\t{}\n{}\n'.format(time_stamp,method.exchange,method.routing_key,json.dumps(body_dict,ensure_ascii=False)))
        #f.write(msgpack.packb((method.exchange, method.routing_key, body)))
    print(method.exchange, method.routing_key, body)
    print("-------------------------------------------------")

mq = MessageQueue('asr-logger')

mq.bind_queue(exchange=settings['messaging']['pre_processing'], routing_key="*.*.*", callback_wrapper_func=callback)
mq.bind_queue(exchange=settings['messaging']['sensors'], routing_key="*.*.*", callback_wrapper_func=callback)
mq.bind_queue(exchange=settings['messaging']['wizard'], routing_key="*.*", callback_wrapper_func=callback)
mq.bind_queue(exchange=settings['messaging']['environment'], routing_key="*.*.*", callback_wrapper_func=callback)
mq.bind_queue(exchange=settings['messaging']['dialogue'], routing_key="*.*", callback_wrapper_func=callback)


print('[*] Waiting for messages. To exit press CTRL+C')
mq.listen()
