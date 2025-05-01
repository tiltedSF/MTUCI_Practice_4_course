from flask import (render_template, request, send_file, Response, 
                   current_app, redirect, url_for, send_from_directory, jsonify)
from werkzeug.utils import secure_filename
from contextlib import closing
from app.models import get_db
from datetime import datetime
import pandas as pd
import cv2
import os
import uuid
from threading import Thread
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def init_routes(app, model):
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/upload', methods=['POST'])
    def upload():
        if 'file' not in request.files:
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_folder = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)
            img_path = os.path.join(upload_folder, filename)
            file.save(img_path)
            
            from app.utils import process_image
            detections, output_img = process_image(img_path, current_app.config['model'])
            
            with closing(get_db()) as conn:
                relative_path = os.path.relpath(output_img, start='app/static')
                conn.execute(
                    "INSERT INTO detections (timestamp, animals_count, classes, image_path) VALUES (?, ?, ?, ?)",
                    (datetime.now().isoformat(), len(detections), 
                     ','.join([d['class'] for d in detections]), relative_path)
                )
                conn.commit()
            
            return render_template('results.html',
                                img_path=relative_path.replace('\\', '/'), 
                                detections=detections)
        
        return redirect(request.url)

    @app.route('/video_feed')
    def video_feed():
        return Response(gen_frames(model), mimetype='multipart/x-mixed-replace; boundary=frame')

    def gen_frames(yolo_model):
        cap = cv2.VideoCapture(0)
        while True:
            success, frame = cap.read()
            if not success: break
            
            try:
                results = yolo_model(frame)
                for box in results[0].boxes:
                    if results[0].names[int(box.cls[0])] in ['cat', 'dog']:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            except Exception as e:
                app.logger.error(f"Frame error: {str(e)}")
                continue
            
            ret, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    @app.route('/report')
    def generate_report():
        try:
            report_dir = os.path.join(current_app.root_path, 'static', 'reports')
            os.makedirs(report_dir, exist_ok=True)
            
            with closing(get_db()) as conn:
                df = pd.read_sql("SELECT * FROM detections", conn)
                excel_path = os.path.join(report_dir, 'detections_report.xlsx')
                df.to_excel(excel_path, index=False, engine='openpyxl')
                
                return send_from_directory(
                    directory=report_dir,
                    path='detections_report.xlsx',
                    as_attachment=True,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                
        except Exception as e:
            current_app.logger.error(f"Report error: {str(e)}")
            return "Error generating report", 500

    @app.route('/upload_video', methods=['POST'])
    def upload_video():
        if 'file' not in request.files:
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            try:
                job_id = str(uuid.uuid4())
                app = current_app._get_current_object()
                
                # Сохраняем временный файл
                temp_dir = os.path.join(app.root_path, 'static', 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                filename = secure_filename(file.filename)
                video_path = os.path.join(temp_dir, filename)
                file.save(video_path)
                
                # Инициализируем задачу
                app.config.setdefault('video_jobs', {})
                app.config['video_jobs'][job_id] = {
                    'status': 'processing',
                    'progress': 0,
                    'filename': None,
                    'path': None,
                    'error': None
                }
                
                # Запускаем обработку в отдельном потоке
                thread = Thread(
                    target=process_video_task,
                    args=(app, video_path, job_id)
                )
                thread.start()
                
                return jsonify({
                    'status': 'processing',
                    'job_id': job_id,
                    'download_url': url_for('download_video', job_id=job_id)
                })
                
            except Exception as e:
                current_app.logger.error(f"Upload error: {str(e)}")
                return jsonify({'error': str(e)}), 500
        
        return redirect(request.url)

    @app.route('/download/<job_id>')
    def download_video(job_id):
        job = current_app.config['video_jobs'].get(job_id)
        if not job:
            return "Job not found", 404
            
        if job['status'] != 'completed':
            return "Video not ready", 202
            
        return send_from_directory(
            directory=os.path.dirname(job['path']),
            path=job['filename'],
            as_attachment=True,
            mimetype='video/mp4'
        )

    @app.route('/status/<job_id>')
    def video_status(job_id):
        job = current_app.config['video_jobs'].get(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
            
        return jsonify(job)

    def allowed_file(filename):
        return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in {'jpg', 'jpeg', 'png', 'mp4', 'avi', 'mov'}

def process_video_task(app, video_path, job_id):
    with app.app_context():
        try:
            from app.utils import process_video
            result_path = process_video(video_path, app.config['model'], job_id)
            
            app.config['video_jobs'][job_id].update({
                'status': 'completed',
                'filename': os.path.basename(result_path),
                'path': result_path,
                'progress': 100
            })
            
            os.remove(video_path)
        except Exception as e:
            app.config['video_jobs'][job_id].update({
                'status': 'failed',
                'error': str(e)
            })