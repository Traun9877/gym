from flask import Flask, render_template, Response, request, jsonify
import cv2
import base64
import numpy as np
import json
import threading
import time
import os
from werkzeug.utils import secure_filename
from pose_estimation.estimation import PoseEstimator
from exercises.squat import Squat
from exercises.hammer_curl import HammerCurl
from exercises.push_up import PushUp
from feedback.layout import layout_indicators
from feedback.information import get_exercise_info
from utils.draw_text_with_background import draw_text_with_background

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class FitnessTrainer:
    def __init__(self):
        self.pose_estimator = PoseEstimator()
        self.exercise = None
        self.exercise_type = None
        self.camera = None
        self.is_running = False
        self.exercise_info = {}
        self.video_source = 0  # 0 for camera, file path for video
        self.video_fps = 30
        self.current_frame_index = 0
        self.total_frames = 0
        self.is_video_file = False
        
    def initialize_exercise(self, exercise_type):
        """Initialize the selected exercise"""
        self.exercise_type = exercise_type
        
        if exercise_type == "hammer_curl":
            self.exercise = HammerCurl()
        elif exercise_type == "squat":
            self.exercise = Squat()
        elif exercise_type == "push_up":
            self.exercise = PushUp()
        else:
            return False
            
        self.exercise_info = get_exercise_info(exercise_type)
        return True
    
    def start_camera(self):
        """Start the camera"""
        try:
            self.video_source = 0
            self.is_video_file = False
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                return False
            self.is_running = True
            self.current_frame_index = 0
            return True
        except Exception as e:
            print(f"Error starting camera: {e}")
            return False
    
    def start_video(self, video_path):
        """Start video file processing"""
        try:
            if not os.path.exists(video_path):
                return False
                
            self.video_source = video_path
            self.is_video_file = True
            self.camera = cv2.VideoCapture(video_path)
            if not self.camera.isOpened():
                return False
                
            # Get video properties
            self.video_fps = self.camera.get(cv2.CAP_PROP_FPS)
            self.total_frames = int(self.camera.get(cv2.CAP_PROP_FRAME_COUNT))
            self.current_frame_index = 0
            self.is_running = True
            return True
        except Exception as e:
            print(f"Error starting video: {e}")
            return False
    
    def stop_camera(self):
        """Stop the camera or video"""
        self.is_running = False
        if self.camera:
            self.camera.release()
            self.camera = None
        self.current_frame_index = 0
        self.total_frames = 0
    
    def get_video_info(self):
        """Get video information"""
        if self.is_video_file and self.camera:
            return {
                'is_video_file': True,
                'total_frames': self.total_frames,
                'current_frame': self.current_frame_index,
                'fps': self.video_fps,
                'duration': self.total_frames / self.video_fps if self.video_fps > 0 else 0,
                'progress': (self.current_frame_index / self.total_frames * 100) if self.total_frames > 0 else 0
            }
        return {
            'is_video_file': False,
            'current_frame': self.current_frame_index
        }
    
    def seek_to_frame(self, frame_number):
        """Seek to specific frame in video"""
        if self.is_video_file and self.camera and 0 <= frame_number < self.total_frames:
            self.camera.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            self.current_frame_index = frame_number
            return True
        return False
    
    def process_frame(self):
        """Process a single frame and return encoded image with exercise data"""
        if not self.camera or not self.is_running:
            return None, {}, {}
            
        ret, frame = self.camera.read()
        if not ret:
            if self.is_video_file:
                # Video ended, stop processing
                self.is_running = False
            return None, {}, {}
        
        # Update frame counter
        self.current_frame_index += 1
        
        # Flip frame horizontally for camera (mirror effect)
        if not self.is_video_file:
            frame = cv2.flip(frame, 1)
        
        exercise_data = {
            'counter': 0,
            'angle': 0,
            'stage': 'Waiting',
            'counter_left': 0,
            'counter_right': 0,
            'angle_left': 0,
            'angle_right': 0,
            'warning_left': '',
            'warning_right': '',
            'progress_left': 0,
            'progress_right': 0,
            'stage_left': 'Waiting',
            'stage_right': 'Waiting'
        }
        
        # Estimate pose
        results = self.pose_estimator.estimate_pose(frame, self.exercise_type)
        
        if results.pose_landmarks and self.exercise:
            # Track exercise based on type
            if self.exercise_type == "squat":
                counter, angle, stage = self.exercise.track_squat(results.pose_landmarks.landmark, frame)
                exercise_data.update({
                    'counter': counter,
                    'angle': round(angle, 1),
                    'stage': stage
                })
                layout_indicators(frame, self.exercise_type, (counter, angle, stage))
                
            elif self.exercise_type == "hammer_curl":
                (counter_right, angle_right, counter_left, angle_left,
                 warning_message_right, warning_message_left, 
                 progress_right, progress_left, stage_right, stage_left) = self.exercise.track_hammer_curl(
                    results.pose_landmarks.landmark, frame)
                
                exercise_data.update({
                    'counter_right': counter_right,
                    'angle_right': round(angle_right, 1),
                    'counter_left': counter_left,
                    'angle_left': round(angle_left, 1),
                    'warning_right': warning_message_right,
                    'warning_left': warning_message_left,
                    'progress_right': progress_right,
                    'progress_left': progress_left,
                    'stage_right': stage_right,
                    'stage_left': stage_left
                })
                layout_indicators(frame, self.exercise_type,
                                  (counter_right, angle_right, counter_left, angle_left,
                                   warning_message_right, warning_message_left, 
                                   progress_right, progress_left, stage_right, stage_left))
                                   
            elif self.exercise_type == "push_up":
                counter, angle, stage = self.exercise.track_push_up(results.pose_landmarks.landmark, frame)
                exercise_data.update({
                    'counter': counter,
                    'angle': round(angle, 1),
                    'stage': stage
                })
                layout_indicators(frame, self.exercise_type, (counter, angle, stage))
        
        # Draw exercise information
        draw_text_with_background(frame, f"Exercise: {self.exercise_info.get('name', 'N/A')}", (40, 50),
                                  cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255,), (118, 29, 14, 0.79), 1)
        draw_text_with_background(frame, f"Target Reps: {self.exercise_info.get('reps', 0)}", (40, 80),
                                  cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255,), (118, 29, 14, 0.79), 1)
        draw_text_with_background(frame, f"Target Sets: {self.exercise_info.get('sets', 0)}", (40, 110),
                                  cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255,), (118, 29, 14, 0.79), 1)
        
        # Add video progress info if it's a video file
        if self.is_video_file:
            progress_text = f"Frame: {self.current_frame_index}/{self.total_frames}"
            draw_text_with_background(frame, progress_text, (40, 140),
                                      cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255,), (118, 29, 14, 0.79), 1)
        
        # Encode frame as JPEG
        _, buffer = cv2.imencode('.jpg', frame)
        frame_encoded = base64.b64encode(buffer).decode('utf-8')
        
        # Get video info
        video_info = self.get_video_info()
        
        return frame_encoded, exercise_data, video_info

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_video', methods=['POST'])
def upload_video():
    """Upload video file"""
    if 'video' not in request.files:
        return jsonify({'success': False, 'message': 'No video file provided'})
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'success': True, 'message': 'Video uploaded successfully', 'filepath': filepath})
    
    return jsonify({'success': False, 'message': 'Invalid file type. Allowed types: mp4, avi, mov, mkv, wmv, flv, webm'})

@app.route('/start_exercise', methods=['POST'])
def start_exercise():
    """Start the exercise with selected type and source"""
    data = request.get_json()
    exercise_type = data.get('exercise_type')
    source_type = data.get('source_type', 'camera')  # 'camera' or 'video'
    video_path = data.get('video_path')
    
    if not exercise_type:
        return jsonify({'success': False, 'message': 'Exercise type required'})
    
    # Initialize exercise
    if not trainer.initialize_exercise(exercise_type):
        return jsonify({'success': False, 'message': 'Invalid exercise type'})
    
    # Start appropriate source
    if source_type == 'video' and video_path:
        if not trainer.start_video(video_path):
            return jsonify({'success': False, 'message': 'Failed to start video processing'})
    else:
        if not trainer.start_camera():
            return jsonify({'success': False, 'message': 'Failed to start camera'})
    
    return jsonify({
        'success': True, 
        'message': f'Started {exercise_type.replace("_", " ").title()}',
        'exercise_info': trainer.exercise_info,
        'video_info': trainer.get_video_info()
    })

@app.route('/stop_exercise', methods=['POST'])
def stop_exercise():
    """Stop the current exercise"""
    trainer.stop_camera()
    return jsonify({'success': True, 'message': 'Exercise stopped'})

@app.route('/get_frame')
def get_frame():
    """Get current frame and exercise data"""
    if not trainer.is_running:
        return jsonify({'success': False, 'message': 'No active session'})
    
    frame_encoded, exercise_data, video_info = trainer.process_frame()
    
    if frame_encoded is None:
        if trainer.is_video_file:
            return jsonify({'success': False, 'message': 'Video playback finished', 'video_ended': True})
        return jsonify({'success': False, 'message': 'Failed to get frame'})
    
    return jsonify({
        'success': True,
        'frame': frame_encoded,
        'exercise_data': exercise_data,
        'exercise_info': trainer.exercise_info,
        'video_info': video_info
    })

@app.route('/seek_video', methods=['POST'])
def seek_video():
    """Seek to specific frame in video"""
    data = request.get_json()
    frame_number = data.get('frame_number', 0)
    
    if trainer.seek_to_frame(frame_number):
        return jsonify({'success': True, 'message': f'Seeked to frame {frame_number}'})
    
    return jsonify({'success': False, 'message': 'Failed to seek or not a video file'})

@app.route('/get_status')
def get_status():
    """Get current status"""
    return jsonify({
        'is_running': trainer.is_running,
        'exercise_type': trainer.exercise_type,
        'exercise_info': trainer.exercise_info,
        'video_info': trainer.get_video_info()
    })

# Global fitness trainer instance
trainer = FitnessTrainer()

if __name__ == '__main__':
    try:
        app.run(debug=True, host='0.0.0.0', port=8000, threaded=True)
    finally:
        trainer.stop_camera()
