import cv2
import os
from flask import current_app
import numpy as np
import torch

def process_image(img_path, yolo_model):
    img = cv2.imread(img_path)
    if img is None:
        raise ValueError(f"Image not found: {img_path}")
    
    results = yolo_model(img)
    detections = []
    
    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            if result.names[cls_id] in ['cat', 'dog']:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"{result.names[cls_id]} {float(box.conf[0]):.2f}"
                cv2.putText(img, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                detections.append({
                    'class': result.names[cls_id],
                    'confidence': float(box.conf[0]),
                    'bbox': [x1, y1, x2, y2]
                })
    
    output_dir = os.path.join(current_app.root_path, 'static', 'results')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, os.path.basename(img_path))
    cv2.imwrite(output_path, img)
    
    return detections, output_path

def process_video(video_path, model, job_id=None):
    output_dir = os.path.join(current_app.root_path, 'static', 'results', 'videos')
    os.makedirs(output_dir, exist_ok=True)
    
    output_name = f'processed_{job_id or "temp"}_{os.path.basename(video_path)}'
    output_path = os.path.join(output_dir, output_name)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Can't open video: {video_path}")
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    try:
        for frame_num in range(int(total_frames)):
            ret, frame = cap.read()
            if not ret:
                break
            
            try:
                # Используем стандартный predict интерфейс YOLO
                results = model(frame, imgsz=640, verbose=False)
                
                # Обработка результатов
                for result in results:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        if result.names[cls_id] in ['cat', 'dog']:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            label = f"{result.names[cls_id]} {float(box.conf[0]):.2f}"
                            cv2.putText(frame, label, (x1, y1-10), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            except Exception as e:
                current_app.logger.error(f"Frame {frame_num} error: {str(e)}")
                continue
            
            out.write(frame)
            
            if job_id:
                progress = int((frame_num / total_frames) * 100)
                current_app.config['video_jobs'][job_id]['progress'] = progress
                
    finally:
        cap.release()
        out.release()
    
    return output_path

def letterbox(im, new_shape=(640, 640), color=(114, 114, 114), auto=True, scaleFill=False, scaleup=True, stride=32):
    # Ресайз с сохранением пропорций (оригинальная реализация из YOLO)
    shape = im.shape[:2]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)
    
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    if not scaleup:
        r = min(r, 1.0)
    
    ratio = r, r
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    
    if auto:
        dw, dh = np.mod(dw, stride), np.mod(dh, stride)
    elif scaleFill:
        dw, dh = 0.0, 0.0
        new_unpad = (new_shape[1], new_shape[0])
        ratio = new_shape[1] / shape[1], new_shape[0] / shape[0]
    
    dw /= 2
    dh /= 2
    
    if shape[::-1] != new_unpad:
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return im, ratio, (dw, dh)

def scale_coords(img1_shape, coords, img0_shape, ratio_pad=None):
    # Масштабирование координат из YOLO
    if ratio_pad is None:
        gain = min(img1_shape[0] / img0_shape[0], img1_shape[1] / img0_shape[1])
        pad = (img1_shape[1] - img0_shape[1] * gain) / 2, (img1_shape[0] - img0_shape[0] * gain) / 2
    else:
        gain = ratio_pad[0][0]
        pad = ratio_pad[1]
    
    coords[:, [0, 2]] -= pad[0]
    coords[:, [1, 3]] -= pad[1]
    coords[:, :4] /= gain
    clip_coords(coords, img0_shape)
    return coords

def clip_coords(boxes, shape):
    # Обрезка координат до границ изображения
    if isinstance(boxes, torch.Tensor):
        boxes[:, 0].clamp_(0, shape[1])
        boxes[:, 1].clamp_(0, shape[0])
        boxes[:, 2].clamp_(0, shape[1])
        boxes[:, 3].clamp_(0, shape[0])
    else:
        boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, shape[1])
        boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, shape[0])