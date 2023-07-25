# -*- coding: utf-8 -*-
# YOLOv5 🚀 by Ultralytics, AGPL-3.0 license

"""
Run YOLOv5 segmentation inference on images, videos, directories, streams, etc.

Usage - sources:
    $ python segment/predict.py --weights yolov5s-seg.pt --source 0                               # webcam
                                                                  img.jpg                         # image
                                                                  vid.mp4                         # video
                                                                  screen                          # screenshot
                                                                  path/                           # directory
                                                                  list.txt                        # list of images
                                                                  list.streams                    # list of streams
                                                                  'path/*.jpg'                    # glob
                                                                  'https://youtu.be/Zgi9g1ksQHc'  # YouTube
                                                                  'rtsp://example.com/media.mp4'  # RTSP, RTMP, HTTP stream

Usage - formats:
    $ python segment/predict.py --weights yolov5s-seg.pt                 # PyTorch
                                          yolov5s-seg.torchscript        # TorchScript
                                          yolov5s-seg.onnx               # ONNX Runtime or OpenCV DNN with --dnn
                                          yolov5s-seg_openvino_model     # OpenVINO
                                          yolov5s-seg.engine             # TensorRT
                                          yolov5s-seg.mlmodel            # CoreML (macOS-only)
                                          yolov5s-seg_saved_model        # TensorFlow SavedModel
                                          yolov5s-seg.pb                 # TensorFlow GraphDef
                                          yolov5s-seg.tflite             # TensorFlow Lite
                                          yolov5s-seg_edgetpu.tflite     # TensorFlow Edge TPU
                                          yolov5s-seg_paddle_model       # PaddlePaddle
"""

import argparse
import os
import platform
import sys
import logging
import time
import threading

from pathlib import Path

import sys

from rplidar import RPLidar
PORT_NAME = '/dev/ttyUSB0'
lidar = RPLidar(PORT_NAME)

#from queue import Queue

from pymavlink import mavutil

import serial as ser

import torch

FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]  # YOLOv5 root directory
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # add ROOT to PATH
ROOT = Path(os.path.relpath(ROOT, Path.cwd()))  # relative

from handlers.threadHandler import ThreadHandler
from models.imgRecModel import ImgRecModel
from models.common import DetectMultiBackend
from utils.dataloaders import IMG_FORMATS, VID_FORMATS, LoadImages, LoadScreenshots, LoadStreams
from utils.general import (LOGGER, Profile, check_file, check_img_size, check_imshow, check_requirements, colorstr, cv2,
                           increment_path, non_max_suppression, print_args, scale_boxes, scale_segments,
                           strip_optimizer)
from utils.plots import Annotator, colors, save_one_box
from utils.segment.general import masks2segments, process_mask, process_mask_native
from utils.torch_utils import select_device, smart_inference_mode

@smart_inference_mode()
def run(
    weights=ROOT / 'yolov5s-seg.pt',  # model.pt path(s)
    source=ROOT / 'data/images',  # file/dir/URL/glob/screen/0(webcam)
    data=ROOT / 'data/coco128.yaml',  # dataset.yaml path
    imgsz=(640, 640),  # inference size (height, width)
    conf_thres=0.25,  # confidence threshold
    iou_thres=0.45,  # NMS IOU threshold
    max_det=1000,  # maximum detections per image
    device='',  # cuda device, i.e. 0 or 0,1,2,3 or cpu
    view_img=False,  # show results
    save_txt=False,  # save results to *.txt
    save_conf=False,  # save confidences in --save-txt labels
    save_crop=False,  # save cropped prediction boxes
    nosave=False,  # do not save images/videos
    classes=None,  # filter by class: --class 0, or --class 0 2 3
    agnostic_nms=False,  # class-agnostic NMS
    augment=False,  # augmented inference
    visualize=False,  # visualize features
    update=False,  # update all models
    project=ROOT / 'runs/predict-seg',  # save results to project/name
    name='exp',  # save results to project/name
    exist_ok=False,  # existing project/name ok, do not increment
    line_thickness=3,  # bounding box thickness (pixels)
    hide_labels=False,  # hide labels
    hide_conf=False,  # hide confidences
    half=False,  # use FP16 half-precision inference
    dnn=False,  # use OpenCV DNN for ONNX inference
    vid_stride=1,  # video frame-rate stride
    retina_masks=False,
):
    
    #########################################Functions################################

# Arm  armBlueRov2
def arm():
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        1, 0, 0, 0, 0, 0, 0)


# Disarm
def disarm():
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        0, 0, 0, 0, 0, 0, 0)

master = mavutil.mavlink_connection('udpin:0.0.0.0:14567')
master.wait_heartbeat()

# Create a function to send RC values
# More information about Joystick channels
# here: https://www.ardusub.com/operators-manual/rc-input-and-output.html#rc-inputs
def set_rc_channel_pwm(channel_id, pwm=1500):
    """ Set RC channel pwm value
    Args:
        channel_id (TYPE): Channel ID
        pwm (int, optional): Channel pwm value 1100-1900
    """
    if channel_id < 1 or channel_id > 8:
        print("Channel does not exist.")
        return

    # Mavlink 2 supports up to 18 channels:
    # https://mavlink.io/en/messages/common.html#RC_CHANNELS_OVERRIDE
    rc_channel_values = [65535 for _ in range(18)]
    for i in range(6):
        rc_channel_values[i] = 1500
    rc_channel_values[channel_id - 1] = pwm
    # print(rc_channel_values)
    master.mav.rc_channels_override_send(
        master.target_system,  # target_system
        master.target_component,  # target_component
        *rc_channel_values)  # RC channel list, in microseconds.


def clear_motion(stopped_pwm=1500):
    ''' Sets all 6 motion direction RC inputs to 'stopped_pwm'. '''
    rc_channel_values = [65535 for _ in range(18)]
    for i in range(6):
        rc_channel_values[i] = stopped_pwm

    master.mav.rc_channels_override_send(
        master.target_system,  # target_system
        master.target_component,  # target_component
        *rc_channel_values)  # RC channel list, in microseconds.
    # print('clear_motion')


def change_mode(mode='MANUAL'):
    """
    :param mode: 'MANUAL' or 'STABILIZE' or 'ALT_HOLD'
    """
    if mode not in master.mode_mapping():
        print("Unknown mode : {}".format(mode))
        print('Try: ', list(master.mode_mapping().keys()))
        sys.exit(1)
    mode_id = master.mode_mapping()[mode]
    master.mav.set_mode_send(
        master.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id)

    while True:
        # Wait for ACK command
        ack_msg = master.recv_match(type='COMMAND_ACK', blocking=True)
        ack_msg = ack_msg.to_dict()
        # Check if command in the same in `set_mode`
        if ack_msg['command'] == mavutil.mavlink.MAVLINK_MSG_ID_SET_MODE:
            print('success')
            break


def request_message_interval(message_id, frequency_hz):
    """
    Request MAVLink message in a desired frequency,
    documentation for SET_MESSAGE_INTERVAL:
        https://mavlink.io/en/messages/common.html#MAV_CMD_SET_MESSAGE_INTERVAL

    Args:
        message_id (int): MAVLink message ID
        frequency_hz (float): Desired frequency in Hz
    """
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
        message_id,  # The MAVLink message ID
        1e6 / frequency_hz,
        # The interval between two messages in microseconds. Set to -1 to disable and 0 to request default rate.
        0,
        # Target address of message stream (if message has target address fields). 0: Flight-stack default (recommended), 1: address of requestor, 2: broadcast.
        0, 0, 0, 0)

    lidar.stop()
    source = str(source)
    save_img = not nosave and not source.endswith('.txt')  # save inference images
    is_file = Path(source).suffix[1:] in (IMG_FORMATS + VID_FORMATS)
    is_url = source.lower().startswith(('rtsp://', 'rtmp://', 'http://', 'https://'))
    webcam = source.isnumeric() or source.endswith('.streams') or (is_url and not is_file)
    screenshot = source.lower().startswith('screen')
    if is_url and is_file:
        source = check_file(source)  # download

    threadHandler = ThreadHandler()
    print(threadHandler.f())

    # Directories
    save_dir = increment_path(Path(project) / name, exist_ok=exist_ok)  # increment run
    (save_dir / 'labels' if save_txt else save_dir).mkdir(parents=True, exist_ok=True)  # make dir

    # Load model
    device = select_device(device)
    model = DetectMultiBackend(weights, device=device, dnn=dnn, data=data, fp16=half)
    stride, names, pt = model.stride, model.names, model.pt
    imgsz = check_img_size(imgsz, s=stride)  # check image size

    # Dataloader
    bs = 1  # batch_size
    if webcam:
        view_img = check_imshow(warn=True)
        dataset = LoadStreams(source, img_size=imgsz, stride=stride, auto=pt, vid_stride=vid_stride)
        bs = len(dataset)
    elif screenshot:
        dataset = LoadScreenshots(source, img_size=imgsz, stride=stride, auto=pt)
    else:
        dataset = LoadImages(source, img_size=imgsz, stride=stride, auto=pt, vid_stride=vid_stride)
    vid_path, vid_writer = [None] * bs, [None] * bs

    # Run inference
    model.warmup(imgsz=(1 if pt else bs, 3, *imgsz))  # warmup
    seen, windows, dt = 0, [], (Profile(), Profile(), Profile())
    
    hope = lidar.iter_measures(max_buf_meas=30000)

    big = False
    #q = Queue(maxsize = 5)



    try:
        #print('Recording measurments... Press Crl+C to stop.')
        imgRecModel = ImgRecModel(weights, source, data, imgsz, conf_thres, iou_thres, max_det, device, view_img, save_txt, save_conf, save_crop, nosave, classes, agnostic_nms, augment, visualize, update, project, name, exist_ok, line_thickness, hide_labels, hide_conf, half, dnn, vid_stride, retina_masks)
        imgRecThread = threading.Thread(target=imgRec, args=(imgRecModel, dataset, big, dt, model, seen, webcam, save_dir, names, windows, save_img), daemon=True)
                
        for measurment in hope:
            
            angle = measurment[2]
            dis = measurment[3]
            
            if(angle > 340 or angle < 20) and (dis != 0 and dis < 1000):
                #print("made it in big")
                if (not( imgRecThread.is_alive() )):
                    #print ("Creating new thread!")
                    imgRecThread = threading.Thread(target=imgRec, args=(imgRecModel, dataset, big, dt, model, seen, webcam, save_dir, names, windows, save_img), daemon=True)
                    imgRecThread.start()

                    """ Que and attempt to show detected frames
                    p = q.get()
                    im0 = q.get()
                    det = q.get()
                    s = q.get()
                    big = q.get()
                    print(big)
                    if (big):
                        print(im0)
                        if imgRecModel.view_img:
                            if platform.system() == 'Linux' and p not in windows:
                                print ("Appending windows")
                                windows.append(p)
                                print ("Naming window")
                                cv2.namedWindow(str(p), cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)  # allow window resize (Linux)
                                print ("Resizing window")
                                cv2.resizeWindow(str(p), im0.shape[1], im0.shape[0])
                        cv2.imshow(str(p), im0)
                        print("I think it is this")
                        cv2.waitKey(1)
                        cv2.destroyAllWindows()
                        # if cv2.waitKey(1) == ord('q'):  # 1 millisecond
                            # print ("Exiting")
                            # exit()
                        # Print time (inference-only)
                        print ("View image completed")
                        
                        big = False
                        """
    except KeyboardInterrupt:
        print('\nStopping.')
        lidar.stop()

def imgRec(imgRecModel, dataset, big, dt, model, seen, webcam, save_dir, names, windows, save_img):
    #print ("Img Rec!")
    for path, im, im0s, vid_cap, s in dataset:
        #print ("Whatever works")
        if big:
            #print("Is BIG")
            return

        with dt[0]:
            im = torch.from_numpy(im).to(model.device)
            im = im.half() if model.fp16 else im.float()  # uint8 to fp16/32
            im /= 255  # 0 - 255 to 0.0 - 1.0
            if len(im.shape) == 3:
                im = im[None]  # expand for batch dim

        #print ("DT 0 Completed")
        # Inference
        with dt[1]:
            imgRecModel.visualize = increment_path(save_dir / Path(path).stem, mkdir=True) if imgRecModel.visualize else False
            pred, proto = model(im, augment=imgRecModel.augment, visualize=imgRecModel.visualize)[:2]

        #print ("DT 1 Completed")
        # NMS
        with dt[2]:
            pred = non_max_suppression(pred, imgRecModel.conf_thres, imgRecModel.iou_thres, imgRecModel.classes, imgRecModel.agnostic_nms, max_det=imgRecModel.max_det, nm=32)

        # Second-stage classifier (optional)
        # pred = utils.general.apply_classifier(pred, classifier_model, im, im0s)

        # Process predictions
        
        #print ("DT 2 Completed")
        for i, det in enumerate(pred):  # per image
            #print ("Image read")

            seen += 1
            if webcam:  # batch_size >= 1
                p, im0, frame = path[i], im0s[i].copy(), dataset.count
                s += f'{i}: '
            else:
                p, im0, frame = path, im0s.copy(), getattr(dataset, 'frame', 0)

            #print ("Image aquired.")
            p = Path(p)  # to Path
            save_path = str(save_dir / p.name)  # im.jpg
            txt_path = str(save_dir / 'labels' / p.stem) + ('' if dataset.mode == 'image' else f'_{frame}')  # im.txt
            s += '%gx%g ' % im.shape[2:]  # print string
            imc = im0.copy() if imgRecModel.save_crop else im0  # for save_crop
            annotator = Annotator(im0, line_width=imgRecModel.line_thickness, example=str(names))
            if len(det):
                if imgRecModel.retina_masks:
                    # scale bbox first the crop masks
                    det[:, :4] = scale_boxes(im.shape[2:], det[:, :4], im0.shape).round()  # rescale boxes to im0 size
                    masks = process_mask_native(proto[i], det[:, 6:], det[:, :4], im0.shape[:2])  # HWC
                else:
                    masks = process_mask(proto[i], det[:, 6:], det[:, :4], im.shape[2:], upsample=True)  # HWC
                    det[:, :4] = scale_boxes(im.shape[2:], det[:, :4], im0.shape).round()  # rescale boxes to im0 size

                # Segments
                if imgRecModel.save_txt:
                    segments = [
                        scale_segments(im0.shape if imgRecModel.retina_masks else im.shape[2:], x, im0.shape, normalize=True)
                        for x in reversed(masks2segments(masks))]

                # Print results
                for c in det[:, 5].unique():
                    n = (det[:, 5] == c).sum()  # detections per class
                    s += f"{n} {names[int(c)]}{'s' * (n > 1)}, "  # add to string

                # Mask plotting
                annotator.masks(
                    masks,
                    colors=[colors(x, True) for x in det[:, 5]],
                    im_gpu=torch.as_tensor(im0, dtype=torch.float16).to(imgRecModel.device).permute(2, 0, 1).flip(0).contiguous() /
                    255 if imgRecModel.retina_masks else im[i])

                # Write results
                for j, (*xyxy, conf, cls) in enumerate(reversed(det[:, :6])):
                    if imgRecModel.save_txt:  # Write to file
                        seg = segments[j].reshape(-1)  # (n,2) to (n*2)
                        line = (cls, *seg, conf) if imgRecModel.save_conf else (cls, *seg)  # label format
                        with open(f'{txt_path}.txt', 'a') as f:
                            f.write(('%g ' * len(line)).rstrip() % line + '\n')

                    if save_img or imgRecModel.save_crop or imgRecModel.view_img:  # Add bbox to image
                        c = int(cls)  # integer class
                        label = None if imgRecModel.hide_labels else (names[c] if imgRecModel.hide_conf else f'{names[c]} {conf:.2f}')
                        annotator.box_label(xyxy, label, color=colors(c, True))
                        # annotator.draw.polygon(segments[j], outline=colors(c, True), width=3)
                    if imgRecModel.save_crop:
                        save_one_box(xyxy, imc, file=save_dir / 'crops' / names[c] / f'{p.stem}.jpg', BGR=True)
            
            #print ("Image broken up")
            # Stream results
            im0 = annotator.result()
            cv2.destroyAllWindows()
            
            """ Que variables
            q.put(p)
            q.put(im0)
            q.put(det)
            q.put(s)
            q.put(True)
            """
            
            LOGGER.info(f"{s}{'' if len(det) else 'w'}{dt[1].dt * 1E3:.1f}ms")
            out = (f"{s}{'' if len(det) else 'w'}")
            stuff = out.split(" ")
            print(len(stuff))
            if(len(stuff) <= 3):
                print("Nothing Detected")
                return
            else:
                out = stuff[3][:-1]
                ans = out + " Dectected"
                print(ans)
                try:
                    sers = ser.Serial("/dev/ttyUSB1", 115200)
                    sers.write(ans)
                    if(ans == 'Stop'):
                        set_rc_channel_pwm(3, 1800)
                    if(ans == 'Left'):
                        set_rc_channel_pwm(1, 510)
                    if(ans == 'Right'):
                        set_rc_channel_pwm(1, 0)
                    if(ans == 'Go'):
                        set_rc_channel_pwm(3, 0)

                except Exception as e:
                    print(e)
            print("BREAK!")
            return

def parse_opt():
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', nargs='+', type=str, default=ROOT / 'yolov5s-seg.pt', help='model path(s)')
    parser.add_argument('--source', type=str, default=ROOT / 'data/images', help='file/dir/URL/glob/screen/0(webcam)')
    parser.add_argument('--data', type=str, default=ROOT / 'data/coco128.yaml', help='(optional) dataset.yaml path')
    parser.add_argument('--imgsz', '--img', '--img-size', nargs='+', type=int, default=[640], help='inference size h,w')
    parser.add_argument('--conf-thres', type=float, default=0.25, help='confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='NMS IoU threshold')
    parser.add_argument('--max-det', type=int, default=1000, help='maximum detections per image')
    parser.add_argument('--device', default='', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    parser.add_argument('--view-img', action='store_true', help='show results')
    parser.add_argument('--save-txt', action='store_true', help='save results to *.txt')
    parser.add_argument('--save-conf', action='store_true', help='save confidences in --save-txt labels')
    parser.add_argument('--save-crop', action='store_true', help='save cropped prediction boxes')
    parser.add_argument('--nosave', action='store_true', help='do not save images/videos')
    parser.add_argument('--classes', nargs='+', type=int, help='filter by class: --classes 0, or --classes 0 2 3')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--augment', action='store_true', help='augmented inference')
    parser.add_argument('--visualize', action='store_true', help='visualize features')
    parser.add_argument('--update', action='store_true', help='update all models')
    parser.add_argument('--project', default=ROOT / 'runs/predict-seg', help='save results to project/name')
    parser.add_argument('--name', default='exp', help='save results to project/name')
    parser.add_argument('--exist-ok', action='store_true', help='existing project/name ok, do not increment')
    parser.add_argument('--line-thickness', default=3, type=int, help='bounding box thickness (pixels)')
    parser.add_argument('--hide-labels', default=False, action='store_true', help='hide labels')
    parser.add_argument('--hide-conf', default=False, action='store_true', help='hide confidences')
    parser.add_argument('--half', action='store_true', help='use FP16 half-precision inference')
    parser.add_argument('--dnn', action='store_true', help='use OpenCV DNN for ONNX inference')
    parser.add_argument('--vid-stride', type=int, default=1, help='video frame-rate stride')
    parser.add_argument('--retina-masks', action='store_true', help='whether to plot masks in native resolution')
    opt = parser.parse_args()
    opt.imgsz *= 2 if len(opt.imgsz) == 1 else 1  # expand
    #print_args(vars(opt))
    return opt


def main(opt):
    check_requirements(ROOT / 'requirements.txt', exclude=('tensorboard', 'thop'))
    run(**vars(opt))


if __name__ == '__main__':
    opt = parse_opt()
    main(opt)
