import json
import pika
import zmq
from threading import Thread
from watson_developer_cloud import SpeechToTextV1, AuthorizationV1
from watson_developer_cloud.websocket import RecognizeCallback
import websocket
import msgpack
import time
from twisted.python import log
from twisted.internet import reactor
import sys,os,yaml
sys.path.append('../..')
from shared import MessageQueue
import urllib.parse
from farmi import FarmiUnit,farmi


# Settings
SETTINGS_FILE = '../../settings.yaml'
settings = yaml.safe_load(open(SETTINGS_FILE, 'r').read())

mission_name = settings['mission']['file'].split(os.sep)[-1].split('.')[0]
session_name = '{}.{}'.format(mission_name, settings['speaker']['id'])

log_path = os.path.join(settings['logging']['log_path'], session_name)

if not os.path.isdir(log_path):
    os.makedirs(log_path)
else:
    print('{} already exists, please change id'.format(log_path))
    sys.exit()


DEBUG = False
WATSON_CRED_DIR = '/Users/jdlopes/ibm_cloud'
with open(os.path.join(WATSON_CRED_DIR,'watson_credentials.json')) as f:
    credentials = json.loads(f.read())
if not credentials:
    exit('no credentials')

# speech_to_text = SpeechToTextV1(
#     username=credentials['username'],
#     password=credentials['password']
# )

api_base_url = credentials['url']
authorization = AuthorizationV1(username=credentials['username'], password=credentials['password'])
token = authorization.get_token(url=api_base_url)

class WatsonCallback(RecognizeCallback):

    START_MESSAGE = {
        'action': 'start',
        'content-type': 'audio/l16;rate=16000',
        'word_confidence': True,
        'timestamps': True,
        'continuous': True,
        'interim_results': True,
        'inactivity_timeout ': -1,
        'speaker_labels': True
    }

    def __init__(self,mq_address,api_url,token,on_message_callback):
        RecognizeCallback.__init__(self)
        self.mq_address = mq_address
        self.api_url = api_url
        self.on_message_callback = on_message_callback
        self.token = token

        self._running = True
        self.timer = None
        self.last_timer = None

        thread = Thread(target=self.connect_to_watson)
        thread.deamon = True
        thread.start()

    def run(self, ws):
        context = zmq.Context()
        s = context.socket(zmq.SUB)
        s.setsockopt_string(zmq.SUBSCRIBE, u'')
        s.connect(self.mq_address)

        if DEBUG: print(json.dumps(self.START_MESSAGE))
        ws.send(json.dumps(self.START_MESSAGE).encode('utf-8'))

        while True:
            data = s.recv()
            if data == b'CLOSE':
                print("got CLOSE msg. stopping..")
                self._running = False
                break
            msgdata,timestamp = msgpack.unpackb(data, use_list=False)
            if not self.timer: self.timer = timestamp
            self.last_timer = timestamp
            try:
                ws.send(msgdata, websocket.ABNF.OPCODE_BINARY)
            except websocket._exceptions.WebSocketConnectionClosedException:
                print("couldn't send, restarting...")
                break
        s.close()
        ws.close()
        print("thread terminating...")

    def on_open(self, ws):
        thread = Thread(target = self.run, args=(ws, ))
        thread.deamon = True
        thread.start()

    def on_close(self,ws):

        print('Closing socket')
        self._running = False

    def connect_to_watson(self):

        headers = {'x-watson-learning-opt-out': "true",
                   'Transfer-encoding': "chunked",
                   'X-Watson-Authorization-Token': self.token}

        while self._running:
            try:
                if DEBUG: print('connecting to watson...')
                ws = websocket.WebSocketApp(
                    self.api_url,
                    header=headers,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                    on_open=self.on_open
                )
                ws.run_forever()
            except:
               'restarting'
        print('DONE')

    def on_error(self,ws,error):
        """Print any errors."""
        print('Error received: {}'.format(error))

    def on_data(self, data):
        print(json.dumps(data, indent=2))
        self.on_message_callback({'transcript':'boi','confidence':1.0})

    def on_inactivity_timeout(self, error):
        print('Inactivity timeout: {}'.format(error))

    def on_message(self, ws, m):
        msg = json.loads(str(m))
        if msg.get('error'):
            print('>> {}'.format(msg))

        print(json.dumps(msg,indent=2))

        if msg.get('results'):
            data = {
                'time_start_asr': self.timer,
                'time_until_asr': self.last_timer,
                'transcript': msg['results'][0].get('alternatives', [{}])[0].get('transcript'),
                'final': msg["results"][0]["final"],
                'confidence': msg['results'][0].get('alternatives', [{}])[0].get('confidence')
            }
            if msg["results"][0]["final"]:
                self.timer = None
                self.on_message_callback(data)



speech_to_text = SpeechToTextV1(
    username=credentials['username'],
    password=credentials['password'],
    url=credentials['url']
)

def create_regognition_method_str(api_base_url):
	parsed_url = urllib.parse.urlparse(api_base_url)
	return urllib.parse.urlunparse(("wss", parsed_url.netloc, parsed_url.path + "/v1/recognize", parsed_url.params, parsed_url.query, parsed_url.fragment, ))

recognition_method_url = create_regognition_method_str(credentials['url'])

FARMI_DIRECTORY_SERVICE_IP = '127.0.0.1'
pub = FarmiUnit('asr',local_save=log_path,directory_service_ip=FARMI_DIRECTORY_SERVICE_IP)


@farmi(subscribe='microphone-sensor',directory_service_ip=settings['FARMI_DIRECTORY_SERVICE_IP'])
def audio_handler(subtopic, time_given, data):

    audio_buffer_address = data[0]['address']
    routing_key = data[1]
    participant = routing_key.rsplit('.', 1)[1]

    print(audio_buffer_address)

    def on_message(data):
        if DEBUG: print(data)
        routing_key = 'asr.data' if data["final"] else 'asr.incremental_data'
        pub.send((json.dumps(data),'{}.{}'.format(routing_key,participant)))

    WatsonCallback(audio_buffer_address, recognition_method_url, token, on_message)

print('[*] Waiting for messages. To exit press CTRL+C')
audio_handler()