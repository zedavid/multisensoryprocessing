import json

import msgpack
import zmq
from threading import Thread
from farmi import Subscriber, Publisher
from watson_developer_cloud import SpeechToTextV1, AuthorizationV1
from watson_developer_cloud.websocket import RecognizeCallback, AudioSource
import pyaudio
import sys,os,yaml
import urllib.parse

sys.path.append('../..')
from orca_utils import utils

try:
    from Queue import Queue, Full
except ImportError:
    from queue import Queue, Full



# Settings
SETTINGS_FILE = '../../settings.yaml'
settings = yaml.safe_load(open(SETTINGS_FILE, 'r').read())

mission_name = settings['mission']['file'].split(os.sep)[-1].split('.')[0]
session_name = '{}.{}'.format(mission_name, settings['speaker']['id'])

log_path = os.path.join(settings['logging']['log_path'], session_name)

if not os.path.isdir(log_path):
    os.makedirs(log_path)
#else:
#    print('{} already exists, please change id'.format(log_path))
#    sys.exit()


DEBUG = False
WATSON_CRED_DIR = '/Users/jdlopes/ibm_cloud'
with open(os.path.join(WATSON_CRED_DIR,'asr_jdl_credentials.json')) as f:
    credentials = json.loads(f.read())
if not credentials:
    exit('no credentials')

# setting message queue system
asr_pub = Publisher('asr',local_save=log_path,directory_service_address='tcp://{}:5555'.format(settings['FARMI_DIRECTORY_SERVICE_IP']))

#api_base_url = credentials['url']
#authorization = AuthorizationV1(username=credentials['username'], password=credentials['password'])
#token = authorization.get_token(url=api_base_url)

class WatsonCallback(RecognizeCallback):


    def __init__(self):
        RecognizeCallback.__init__(self)

    def on_transcription(self, transcript):
        pass

    def on_connected(self):
        asr_pub.send(({'text': ''},'action.restart'))
        print('Connection was successful')

    def on_error(self,error):
        """Print any errors."""
        print('Error received: {}'.format(error))

    def on_inactivity_timeout(self, error):
        print('Inactivity timeout: {}'.format(error))

    def on_listening(self):
        print('Service is listening')

    def on_hypothesis(self, hypothesis):
        pass

    def on_data(self, data):
        if 'results' in data:
            for result in data['results']:
                routing_key = 'asr.data' if result['final'] else 'asr.incremental_data'
                trans, final = self._parse_speech_data(data)
                if DEBUG:
                    utils.print_dict({'transcript': trans, 'final': final})
                asr_pub.send((json.dumps({'transcript': trans, 'final': final}),'{}.mic'.format(routing_key)))
        if 'speaker_labels' in data:
            for result in data['speaker_labels']:
                routing_key = 'asr.speaker_labels' if result['final'] else 'asr.incremental_speaker_labels'
                asr_pub.send((json.dumps(data), '{}.mic'.format(routing_key)))

    def _parse_speech_data(self, data):

        one_best = data['results'][0]
        return one_best['alternatives'][0]['transcript'],one_best['final']


    def on_close(self):
        print('Connection closed')


def recognize_using_weboscket(audio_source):

    mycallback = WatsonCallback()
    speech_to_text.recognize_using_websocket(audio=audio_source,
                                             content_type='audio/l16; rate=16000',
                                         recognize_callback=mycallback,
                                         interim_results=True,
                                         word_confidence=True,
                                         timestamps=True,
                                         speaker_labels=True,
                                         inactivity_timeout=settings['asr']['inactivity_timeout'])
speech_to_text = SpeechToTextV1(
    iam_apikey=credentials['apikey'],
    url=credentials['url']
)

def audio_callback(audio_address,audio_queue):

    context = zmq.Context()
    s = context.socket(zmq.SUB)
    s.setsockopt_string(zmq.SUBSCRIBE, u'')
    s.connect(audio_address)

    while True:
        data = s.recv()
        if data == b'CLOSE':
            break
        msgdata, timestamp = msgpack.unpackb(data, use_list=False)
        try:
            audio_queue.put(msgdata)
        except Full:
            pass


def open_recognizer(audio_config):

    q = Queue(maxsize=int(round(audio_config['buf_max_size'],audio_config['chunk'])))
    audio_source = AudioSource(q,True,True)

    audio_thread = Thread(target=audio_callback, args=(audio_config['address'],q))
    audio_thread.start()

    try:
        rec_thread = Thread(target=recognize_using_weboscket, args=(audio_source,))
        rec_thread.start()
        while True:
            pass
    except KeyboardInterrupt:
        audio_source.completed_recording()
        return

def audio_handler(subtopic, time_given, data):

    open_recognizer(data[0])


audio_stream_sub = Subscriber(directory_service_address='tcp://{}:5555'.format(settings['FARMI_DIRECTORY_SERVICE_IP']))
audio_stream_sub.subscribe_to('microphone-sensor', audio_handler)
audio_stream_sub.listen()


