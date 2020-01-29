import argparse

from google.cloud import speech
from google.cloud.speech import types
from google.cloud.speech import enums
import zmq
from threading import Thread
import queue
import json
import time
import msgpack
import sys,yaml
import wave,os,re
from farmi import Subscriber, Publisher
sys.path.append('../..')
from orca_utils import utils

RATE = 16000

# Settings
SETTINGS_FILE = '../../settings.yaml'
settings = yaml.safe_load(open(SETTINGS_FILE, 'r').read())

log_path = os.path.join(settings['logging']['log_path'], settings['speaker']['id'],time.strftime("%Y_%m_%d"))

if not os.path.isdir(log_path):
    os.makedirs(log_path)

asr_pub = Publisher('asr',local_save=log_path,directory_service_address='tcp://{}:5555'.format(settings['FARMI_DIRECTORY_SERVICE_IP']))

#starts google speech client
speech_client = speech.SpeechClient()

STREAMING_LIMIT = 10000

RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[0;33m'

audio_in = []
utt_counter = 0

def get_current_time():
    """Return Current Time in MS."""

    return int(round(time.time() * 1000))


class MicAsBuffer(object):
    def __init__(self, message):

        audio_config = message[0]
        self.routing_ley = message

        self._rate = audio_config['rate']
        self.chunk_size = audio_config['chunk']
        self._num_channels = 1
        self._buff = queue.Queue()
        self.closed = True
        self.start_time = get_current_time()
        self.restart_counter = 0
        self.audio_input = []
        self.last_audio_input = []
        self.result_end_time = 0
        self.is_final_end_time = 0
        self.final_request_end_time = 0
        self.bridging_offset = 0
        self.last_transcript_was_final = False
        self.new_stream = True

        self.address = audio_config['address']

        utils.print_dict(audio_config)

        #self._buff = queue.Queue()
        #self._buff = queue.Queue(maxsize=int(round(audio_config['buf_max_size'],audio_config['chunk'])))

    def __enter__(self):
        self.closed = False
        self.thread = Thread(target = self.socket_thread)
        self.thread.deamon = True
        self.thread.start()  # Execute B
        return self

    def __exit__(self, type, value, traceback):
        self.closed = True
        self._buff.put(None)
        self.thread.join()

    def socket_thread(self):
        context = zmq.Context()
        s = context.socket(zmq.SUB)
        s.setsockopt_string(zmq.SUBSCRIBE, u'')
        s.connect(self.address)
        while not self.closed:
            data = s.recv()
            self._buff.put(msgpack.unpackb(data, use_list=False))

        return None


    def generator(self):
        """Stream Audio from microphone to API and to local buffer"""

        while not self.closed:
            data = []

            if self.new_stream and self.last_audio_input:

                chunk_time = STREAMING_LIMIT / len(self.last_audio_input)

                if chunk_time != 0:

                    if self.bridging_offset < 0:
                        self.bridging_offset = 0

                    if self.bridging_offset > self.final_request_end_time:
                        self.bridging_offset = self.final_request_end_time

                    chunks_from_ms = round((self.final_request_end_time -
                                            self.bridging_offset) / chunk_time)

                    self.bridging_offset = (round((
                        len(self.last_audio_input) - chunks_from_ms)
                                                  * chunk_time))

                    for i in range(chunks_from_ms, len(self.last_audio_input)):
                        data.append(self.last_audio_input[i])

                self.new_stream = False

            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            da, timer = self._buff.get()
            self.audio_input.append(da)

            if da is None:
                return
            data.append(da)
            # Now consume whatever other data's still buffered.
            while True:
                try:
                    da, _ = self._buff.get(block=False)

                    if da is None:
                        return
                    data.append(da)
                    self.audio_input.append(da)

                except queue.Empty:
                    break

            yield b''.join(data)

#    def generator(self):
#        if self.closed:
#            return
#        da, timer = self._buff.get()
#        print(da)
#        if not self.timer: self.timer = timer
#        if da is None:
#            return
#        data = [da]
#        while True:
#            try:
#                new_da, _ = self._buff.get(block=False)
#                if new_da is None:
#                    return
#                data.append(new_da)
#            except queue.Empty:
#                break

 #       self.last_timer = self.timer

        #print(''.join(data))
  #      yield b''.join(data)

parser = argparse.ArgumentParser(description='Receives buffer and streams into google cloud asr')
parser.add_argument('--language','-l',type=str,help='language used by google asr',default='en-GB')

args = parser.parse_args()

config = types.RecognitionConfig(
    encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=RATE,
    language_code=args.language)
streaming_config = types.StreamingRecognitionConfig(
    config=config,
    interim_results=True)

def save_audio():
    waveFile = wave.open(os.path.join(log_path, 'audio_utt_{:03d}.wav'.format(utt_counter)), 'wb')
    waveFile.setnchannels(1)
    waveFile.setsampwidth(2)
    waveFile.setframerate(RATE)
    waveFile.writeframes(b''.join(audio_in))
    waveFile.close()

def listen_print_loop(responses, stream, routing_key):
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.
    """

    for response in responses:

        if get_current_time() - stream.start_time > STREAMING_LIMIT:
            stream.start_time = get_current_time()
            break

        if not response.results:
            continue

        result = response.results[0]

        if not result.alternatives:
            continue

        transcript = result.alternatives[0].transcript
        confidence = result.alternatives[0].confidence

        result_seconds = 0
        result_nanos = 0

        if result.result_end_time.seconds:
            result_seconds = result.result_end_time.seconds

        if result.result_end_time.nanos:
            result_nanos = result.result_end_time.nanos

        stream.result_end_time = int((result_seconds * 1000)
                                     + (result_nanos / 1000000))

        corrected_time = (stream.result_end_time - stream.bridging_offset
                          + (STREAMING_LIMIT * stream.restart_counter))
        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.

        if result.is_final:

            sys.stdout.write(GREEN)
            sys.stdout.write('\033[K')
            sys.stdout.write(str(corrected_time) + ': ' + transcript + '\n')

            asr_pub.send((json.dumps({'transcript': transcript,
                                      'final': result.is_final,
                                      'confidence': confidence}), f'{routing_key}.mic'))

            stream.is_final_end_time = stream.result_end_time
            stream.last_transcript_was_final = True

            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            if re.search(r'\b(exit|quit)\b', transcript, re.I):
                sys.stdout.write(YELLOW)
                sys.stdout.write('Exiting...\n')
                stream.closed = True
                break

        else:
            sys.stdout.write(RED)
            sys.stdout.write('\033[K')
            sys.stdout.write(str(corrected_time) + ': ' + transcript + '\r')
            stream.last_transcript_was_final = False

def audio_handler(subtopic, time_given, data):

    routing_key = data[1]
    participant = routing_key.rsplit('.',1)[1]

    print(f"Getting audio for {data[0]['address']}")

    with MicAsBuffer(data) as stream:

        while not stream.closed:
            sys.stdout.write(YELLOW)
            sys.stdout.write('\n' + str(
                STREAMING_LIMIT * stream.restart_counter) + ': NEW REQUEST\n')

            stream.audio_input = []

            audio_generator = stream.generator()

            requests = (types.StreamingRecognizeRequest(audio_content=chunk)
                        for chunk in audio_generator)

            responses = speech_client.streaming_recognize(streaming_config,requests)


            # Now, put the transcription responses to use.
            listen_print_loop(responses, stream, routing_key)

            if stream.result_end_time > 0:
                stream.final_request_end_time = stream.is_final_end_time
            stream.result_end_time = 0
            stream.last_audio_input = []
            stream.last_audio_input = stream.audio_input
            stream.audio_input = []
            stream.restart_counter = stream.restart_counter + 1

            if not stream.last_transcript_was_final:
                sys.stdout.write('\n')
            stream.new_stream = True

# Let's be on the safe side and recording this to the computer...
audio_stream_sub = Subscriber(directory_service_address='tcp://{}:5555'.format(settings['FARMI_DIRECTORY_SERVICE_IP']))
audio_stream_sub.subscribe_to('microphone-sensor', audio_handler)
audio_stream_sub.listen()



