#!/usr/bin/env python3

"""
Tiny-yolo-v3 device side decoding demo
  YOLO v3 Tiny is a real-time object detection model implemented with Keras* from
  this repository <https://github.com/david8862/keras-YOLOv3-model-set> and converted
  to TensorFlow* framework. This model was pretrained on COCO* dataset with 80 classes.
"""

from pathlib import Path
import sys
import cv2
import depthai as dai
import numpy as np
import time

# yolo v3 and tinty-yolov3 labels
labelMap = [
    "face",
]


syncNN = True

# Get argument first
# nnPath = str((Path(__file__).parent / Path('yolov3-face-OAK/yoloV3/frozen_darknet_yolov3_model.blob')).resolve().absolute())
nnPath = str((Path(__file__).parent / Path('yoloV3-face-OAK/yolov3_tiny/frozen_darknet_yolov3_model.blob')).resolve().absolute())

if len(sys.argv) > 1:
    nnPath = sys.argv[1]

# Start defining a pipeline
pipeline = dai.Pipeline()

# Define a source - color camera
camRgb = pipeline.createColorCamera()
camRgb.setPreviewSize(416, 416)
camRgb.setInterleaved(False)
camRgb.setFps(40)

# network specific settings
detectionNetwork = pipeline.createYoloDetectionNetwork()
detectionNetwork.setConfidenceThreshold(0.5)
detectionNetwork.setNumClasses(1)
detectionNetwork.setCoordinateSize(4)
detectionNetwork.setAnchors(np.array([10,14, 23,27, 37,58, 81,82, 135,169, 344,319]))
detectionNetwork.setAnchorMasks({"side26": np.array([1, 2, 3]), "side13": np.array([3, 4, 5])})
detectionNetwork.setIouThreshold(0.5)

detectionNetwork.setBlobPath(nnPath)
detectionNetwork.setNumInferenceThreads(2)
detectionNetwork.input.setBlocking(False)

camRgb.preview.link(detectionNetwork.input)

# Create outputs
xoutRgb = pipeline.createXLinkOut()
xoutRgb.setStreamName("rgb")
if syncNN:
    detectionNetwork.passthrough.link(xoutRgb.input)
else:
    camRgb.preview.link(xoutRgb.input)

nnOut = pipeline.createXLinkOut()
nnOut.setStreamName("detections")
detectionNetwork.out.link(nnOut.input)


# Pipeline defined, now the device is connected to
with dai.Device(pipeline) as device:
    # Start pipeline
    device.startPipeline()

    # Output queues will be used to get the rgb frames and nn data from the outputs defined above
    qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
    qDet = device.getOutputQueue(name="detections", maxSize=4, blocking=False)

    frame = None
    detections = []

    # nn data, being the bounding box locations, are in <0..1> range - they need to be normalized with frame width/height
    def frameNorm(frame, bbox):
        normVals = np.full(len(bbox), frame.shape[0])
        normVals[::2] = frame.shape[1]
        return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

    def displayFrame(name, frame):
        for detection in detections:
            bbox = frameNorm(frame, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
            cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0,255, 0), 2)
            cv2.putText(frame, labelMap[detection.label], (bbox[0] + 10, bbox[1] + 20), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255,0,0), 2)
            cv2.putText(frame, f"{int(detection.confidence * 100)}%", (bbox[0] + 10, bbox[1] + 40), cv2.FONT_HERSHEY_DUPLEX, 0.3, (0,0,255), 1)
        cv2.imshow(name, frame)

    startTime = time.monotonic()
    counter = 0

    while True:
        if syncNN:
            inRgb = qRgb.get()
            inDet = qDet.get()
        else:
            inRgb = qRgb.tryGet()
            inDet = qDet.tryGet()

        if inRgb is not None:
            frame = inRgb.getCvFrame()
            cv2.putText(frame, "NN fps: {:.2f}".format(counter / (time.monotonic() - startTime)),
                        (2, frame.shape[0] - 4), cv2.FONT_HERSHEY_DUPLEX, 0.4, color=(255, 255, 255))

        if inDet is not None:
            detections = inDet.detections
            counter += 1

        if frame is not None:
            displayFrame("YOLO", frame)

        if cv2.waitKey(1) == ord('q'):
            break

cv2.destroyAllWindows()