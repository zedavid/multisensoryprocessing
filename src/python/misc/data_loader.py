import msgpack
import cv2
import numpy as np
import wave
import pyaudio

#default audio configuration in the CORALL recordings
p = pyaudio.PyAudio()
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 16000
CHUNK = 1440

# default video resolution used in the CORALL recordings
height_cv = 480
width_cv = 640

waveFile = wave.open('test_left.wav', 'wb')
waveFile.setnchannels(1)
waveFile.setsampwidth(p.get_sample_size(FORMAT))
waveFile.setframerate(RATE)


with open('/Users/jdlopes/Sprakkafe/logs/oskar.joan.personal/video.new_sensor.Oskar-0/data.cv-video', 'rb') as f:
    unpacker = msgpack.Unpacker(f)
    for value, timestamp in unpacker:
        #waveFile.writeframes(value)
        print(np.frombuffer(value, dtype='uint8').shape)
        cv2.imshow('data', np.frombuffer(value, dtype='uint8').reshape((height_cv, width_cv, 3)))
        cv2.waitKey(1)
