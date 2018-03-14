import msgpack
import cv2
import numpy as np
import wave
import pyaudio
import argparse,os
import json

#default audio configuration in the CORALL recordings
p = pyaudio.PyAudio()
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 16000
CHUNK = 1440

waveFile = wave.open('test_left.wav', 'wb')
waveFile.setnchannels(1)
waveFile.setsampwidth(p.get_sample_size(FORMAT))
waveFile.setframerate(RATE)

def load_video_raw_data(root_dir, filename):

    file_info = json.load(open(os.path.join(root_dir,'info.txt')))

    height_cv = int(file_info['img_size']['height'])
    width_cv = int(file_info['img_size']['width'])

    try:
        with open(os.path.join(root_dir,filename), 'rb') as f:
            unpacker = msgpack.Unpacker(f)
            for value, timestamp in unpacker:
                cv2.imshow('data', np.frombuffer(value, dtype='uint8').reshape((height_cv, width_cv, 3)))
                cv2.waitKey(1)
    except KeyboardInterrupt:
        cv2.destroyAllWindows()
        return


def load_video_data(filename):
    cap = cv2.VideoCapture(filename)

    try:
        while(cap.isOpened):
            ret, frame = cap.read()
            if ret == True:
                cv2.imshow('frame', frame.reshape((480,640,3)))
                cv2.waitKey(1)
            else:
                break
    except KeyboardInterrupt:
        cap.release()
        cv2.destroyAllWindows()
        return

def load_audio_raw_data(root_dir,filename):
    # open stream
    stream = p.open(format=FORMAT,
                    channels=1,
                    rate=RATE,
                    output=True)

    try:
        with open(os.path.join(root_dir,filename),'rb') as f:
            unpacker = msgpack.Unpacker(f)
            for value, timestamp in unpacker:
                stream.write(value)
    except KeyboardInterrupt:
        stream.close()
        return

def load_audio_data(filename):

    # define stream chunk
    chunk = 1024

    # open a wav format music
    f = wave.open(filename, "rb")
    # instantiate PyAudio
    p = pyaudio.PyAudio()
    # open stream
    stream = p.open(format=p.get_format_from_width(f.getsampwidth()),
                    channels=f.getnchannels(),
                    rate=f.getframerate(),
                    output=True)
    # read data
    data = f.readframes(chunk)

    try:
        # play stream
        while data:
            stream.write(data)
            data = f.readframes(chunk)

    except KeyboardInterrupt:
        # stop stream
        stream.stop_stream()
        stream.close()

        # close PyAudio
        p.terminate()
        return

parser = argparse.ArgumentParser(description='Files in folder')
parser.add_argument('--folder', '-f', type=str,help='folder where the data is stored',required=True)
args = parser.parse_args()

for root,dir,files in os.walk(args.folder):
    for file in files:
        print(os.path.join(root,file))
        if file.endswith('cv-video'):
            load_video_raw_data(root,file)
        if file.endswith('mp4'):
            load_video_data(os.path.join(root,file))
        if file.endswith('data.audio'):
            load_audio_raw_data(root,file)
        if file.endswith('wav'):
            load_audio_data(os.path.join(root,file))

