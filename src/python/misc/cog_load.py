import argparse,json,os
import msgpack
import cv2, dlib
import matplotlib.pyplot as plt
import numpy as np
from imutils import face_utils
import frontalize
import scipy.io as io
import face-frontalization/facial_feature_detector as feature_detector
import face-frontalization/check_resources as check
import face-frontalization/camera_calibration as calib

def open_video_raw_data(root_dir,filename):
    file_info = json.load(open(os.path.join(root_dir,'info.txt')))

    height_cv = int(file_info['img_size']['height'])
    width_cv = int(file_info['img_size']['width'])

    check.check_dlib_landmark_weights()

    try:
        with open(os.path.join(root_dir,filename), 'rb') as f:
            unpacker = msgpack.Unpacker(f)
            for value, timestamp in unpacker:
                reshaped_frame = np.frombuffer(value, dtype='uint8').reshape((height_cv, width_cv, 3))
                lmarks = feature_detector.get_landmarks(reshaped_frame)
                proj_matrix, camera_matrix, rmat, tvec = calib.estimate_camera(frontalizePred)
                eyemask = np.asarray(io.loadmat('frontalizations_models/eyemask.mat')['eyemask'])
                frontal_raw, frontal_sym = frontalize.frontalize(reshaped_frame,proj_matrix,frontalizePred.ref_U,eyemask)
                plt.figure()
                plt.title('Frontalized no symmetry')
                plt.imshow(frontal_raw[:,:,::-1])
                plt.figure()
                plt.title('Frontalized with soft symmetry')
                plt.imshow(frontal_sym[:,:,::-1])
                plt.show()
                #grey_frame = cv2.cvtColor(reshaped_frame,cv2.COLOR_BGR2GRAY)
                # faces = faceCascade.detectMultiScale(
                #     grey_frame,
                #     scaleFactor=1.1,
                #     minNeighbors=5,
                #     minSize=(30, 30),
                #     flags=cv2.CASCADE_SCALE_IMAGE
                # )
#                faces = detector(grey_frame, 1)
#                for (i,face) in enumerate(faces):
#                    shape = shapePredictor(grey_frame,face)
 #                   shape = face_utils.shape_to_np(shape)
  #                  (x,y,w,h) = face_utils.rect_to_bb(face)
   #                 cv2.rectangle(reshaped_frame,(x,y),(x+w,y+h),(0,255,0),2)
   #                 cv2.putText(reshaped_frame, "Face #{}".format(i + 1), (x - 10, y - 10),
#		cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

 #                   for (x,y) in shape:
  #                      cv2.circle(reshaped_frame,(x,y),1,(0,0,255),-1)
   #             cv2.imshow('frame',reshaped_frame)
   #             cv2.waitKey(1)
    except KeyboardInterrupt:
        cv2.destroyAllWindows()
        return

def open_video_data(video_file):
    cap = cv2.VideoCapture(video_file)
    fps = cap.get(cv2.CAP_PROP_FPS)
    try:
        while(cap.isOpened):
            ret, frame = cap.read()
            if ret == True:
                grey_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                cv2.imshow('frame', grey_frame.reshape((480,640,3)))
                cv2.waitKey(1)
            else:
                break
    except KeyboardInterrupt:
        cap.release()
        cv2.destroyAllWindows()
        return

parser = argparse.ArgumentParser(description='Dialogue folder')
parser.add_argument('--folder', '-f', type=str,help='folder where the data is stored',required=True)
parser.add_argument("-p", "--shape-predictor", required=True,
	help="path to facial landmark predictor")
parser.add_argument("-fr","--frontalization-models",required=True,help="path to frontalization model")
args = parser.parse_args()

#faceCascade = cv2.CascadeClassifier('haarcascade_frontalface_alt.xml')
detector = dlib.get_frontal_face_detector()
shapePredictor = dlib.shape_predictor(args.shape_predictor)
frontalize_model_name = args.frontalization_models.split(os.sep)[-1].split('.')[0]
frontalizePred = frontalize.ThreeD_Model(args.frontalization_models,'model_dlib')

for root,dir,files in os.walk(args.folder):
    for file in files:
        if file.endswith('cv-video'):
            open_video_raw_data(root,file)
        if file.endswith('mp4'):
            open_video_data(os.path.join(root,file))
