import cv2
import os
from tkinter import filedialog
import tkinter as tk
from pose_estimation.estimation import PoseEstimator
from exercises.squat import Squat
from exercises.hammer_curl import HammerCurl
from exercises.push_up import PushUp
from feedback.layout import layout_indicators
from feedback.information import get_exercise_info
from utils.draw_text_with_background import draw_text_with_background

def select_exercise():
    """Let user select exercise type"""
    print("\n=== FITNESS TRAINER ===")
    print("Select an exercise:")
    print("1. Squat")
    print("2. Hammer Curl")
    print("3. Push Up")
    
    while True:
        try:
            choice = input("\nEnter your choice (1-3): ").strip()
            if choice == "1":
                return "squat"
            elif choice == "2":
                return "hammer_curl"
            elif choice == "3":
                return "push_up"
            else:
                print("Invalid choice! Please enter 1, 2, or 3.")
        except KeyboardInterrupt:
            print("\nExiting...")
            exit()

def select_video_source():
    """Let user choose between webcam or video file"""
    print("\nSelect video source:")
    print("1. Webcam (Live)")
    print("2. Video File")
    
    while True:
        try:
            choice = input("\nEnter your choice (1-2): ").strip()
            if choice == "1":
                return 0  # Webcam
            elif choice == "2":
                return select_video_file()
            else:
                print("Invalid choice! Please enter 1 or 2.")
        except KeyboardInterrupt:
            print("\nExiting...")
            exit()

def select_video_file():
    """Open file dialog to select video file"""
    print("\nOpening file dialog...")
    
    # Create a root window and hide it
    root = tk.Tk()
    root.withdraw()
    
    # Open file dialog
    file_path = filedialog.askopenfilename(
        title="Select Video File",
        filetypes=[
            ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv"),
            ("MP4 files", "*.mp4"),
            ("AVI files", "*.avi"),
            ("All files", "*.*")
        ]
    )
    
    root.destroy()
    
    if not file_path:
        print("No file selected. Exiting...")
        exit()
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        exit()
    
    return file_path

def get_output_filename(exercise_type, is_webcam):
    """Generate output filename"""
    if is_webcam:
        return f"output_{exercise_type}_webcam.avi"
    else:
        return f"output_{exercise_type}_video.avi"

def main():
    try:
        # Get user selections
        exercise_type = select_exercise()
        video_source = select_video_source()
        
        print(f"\nSelected exercise: {exercise_type.replace('_', ' ').title()}")
        if video_source == 0:
            print("Using webcam")
        else:
            print(f"Using video file: {os.path.basename(video_source)}")
        
        # Initialize video capture
        cap = cv2.VideoCapture(video_source)
        
        if not cap.isOpened():
            print("Error: Could not open video source!")
            return
        
        # Initialize pose estimator
        pose_estimator = PoseEstimator()
        
        # Initialize exercise tracker
        if exercise_type == "hammer_curl":
            exercise = HammerCurl()
        elif exercise_type == "squat":
            exercise = Squat()
        elif exercise_type == "push_up":
            exercise = PushUp()
        else:
            print("Invalid exercise type.")
            return
        
        # Get exercise information
        exercise_info = get_exercise_info(exercise_type)
        
        # Setup video writer for output
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        is_webcam = (video_source == 0)
        output_file = get_output_filename(exercise_type, is_webcam)
        
        # Create output directory if it doesn't exist
        os.makedirs("output", exist_ok=True)
        output_path = os.path.join("output", output_file)
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:  # Some webcams might return 0
            fps = 30
            
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
        
        print(f"\nProcessing... Press 'q' to quit")
        print(f"Output will be saved to: {output_path}")
        
        # Main processing loop
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Estimate pose
            results = pose_estimator.estimate_pose(frame, exercise_type)
            
            if results.pose_landmarks:
                # Track exercise based on type
                if exercise_type == "squat":
                    counter, angle, stage = exercise.track_squat(results.pose_landmarks.landmark, frame)
                    layout_indicators(frame, exercise_type, (counter, angle, stage))
                    
                elif exercise_type == "hammer_curl":
                    (counter_right, angle_right, counter_left, angle_left,
                     warning_message_right, warning_message_left, 
                     progress_right, progress_left, stage_right, stage_left) = exercise.track_hammer_curl(
                        results.pose_landmarks.landmark, frame)
                    layout_indicators(frame, exercise_type,
                                      (counter_right, angle_right, counter_left, angle_left,
                                       warning_message_right, warning_message_left, 
                                       progress_right, progress_left, stage_right, stage_left))
                                       
                elif exercise_type == "push_up":
                    counter, angle, stage = exercise.track_push_up(results.pose_landmarks.landmark, frame)
                    layout_indicators(frame, exercise_type, (counter, angle, stage))
            
            # Draw exercise information
            draw_text_with_background(frame, f"Exercise: {exercise_info.get('name', 'N/A')}", (40, 50),
                                      cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255,), (118, 29, 14, 0.79), 1)
            draw_text_with_background(frame, f"Reps: {exercise_info.get('reps', 0)}", (40, 80),
                                      cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255,), (118, 29, 14, 0.79), 1)
            draw_text_with_background(frame, f"Sets: {exercise_info.get('sets', 0)}", (40, 110),
                                      cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255,), (118, 29, 14, 0.79), 1)
            
            # Write frame to output video
            out.write(frame)
            
            # Display frame
            window_name = f"{exercise_type.replace('_', ' ').title()} Tracker"
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 1280, 720)  # More reasonable size
            cv2.imshow(window_name, frame)
            
            # Exit on 'q' key press
            if cv2.waitKey(10) & 0xFF == ord('q'):
                break
        
        print(f"\nProcessing complete!")
        print(f"Output saved to: {output_path}")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        # Cleanup
        if 'cap' in locals():
            cap.release()
        if 'out' in locals():
            out.release()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()