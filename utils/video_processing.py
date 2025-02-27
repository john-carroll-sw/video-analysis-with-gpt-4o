import cv2
import os
import base64
import streamlit as st
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from moviepy.editor import VideoFileClip
import json
import time
import logging

# Get logger for this module
logger = logging.getLogger(__name__)

def process_video(video_path, frames_per_second=1, resize=4, output_dir=''):
    """Extract and encode frames from a video file."""
    logger.info(f"Processing video: {video_path}")
    
    base64Frames = []

    video = cv2.VideoCapture(video_path)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = video.get(cv2.CAP_PROP_FPS)
    frames_to_skip = int(fps / frames_per_second)
    curr_frame = 0
    frame_count = 1

    while curr_frame < total_frames - 1:
        video.set(cv2.CAP_PROP_POS_FRAMES, curr_frame)
        success, frame = video.read()
        if not success:
            break

        logger.debug(f"Processing frame {curr_frame}/{total_frames}")

        if resize != 0:
            height, width, _ = frame.shape
            frame = cv2.resize(frame, (width // resize, height // resize))

        _, buffer = cv2.imencode(".jpg", frame)

        if output_dir:
            frame_filename = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(video_path))[0]}_frame_{frame_count}.jpg")
            with open(frame_filename, "wb") as f:
                f.write(buffer)
                logger.debug(f"Saved frame: {frame_filename}")
            frame_count += 1

        base64Frames.append(base64.b64encode(buffer).decode("utf-8"))
        curr_frame += frames_to_skip
    video.release()
    
    logger.info(f"Extracted {len(base64Frames)} frames")
    return base64Frames

def process_audio(video_path):
    """Extract and transcribe audio from a video file."""
    logger.info(f"Starting audio transcription for {video_path}")
    transcription_text = ''
    
    try:
        # First check if the video file exists and has audio
        clip = VideoFileClip(video_path)
        if not clip.audio:
            logger.info(f"No audio track found in {video_path}")
            clip.close()
            return "No audio found in this segment."

        # Extract audio to file in the same directory as the video
        base_video_path, _ = os.path.splitext(video_path)
        audio_path = f"{base_video_path}.mp3"
        
        try:
            clip.audio.write_audiofile(audio_path, bitrate="32k", verbose=False, logger=None)
            clip.audio.close()
            clip.close()
            logger.info(f"Extracted audio to {audio_path}")

            # Transcribe the audio
            with open(audio_path, "rb") as audio_file:
                transcription = st.session_state.whisper_client.audio.transcriptions.create(
                    model=st.session_state.whisper_model_name,
                    file=audio_file
                )
                transcription_text = transcription.text
                logger.info(f"Transcription successful: {transcription_text}")
                logger.info(f"Audio file saved at: {audio_path}")

        except Exception as ex:
            logger.error(f'ERROR in audio processing: {str(ex)}')
            if os.path.exists(audio_path):
                os.remove(audio_path)  # Only remove on error
            
    except Exception as ex:
        logger.error(f'ERROR processing audio: {str(ex)}')
        transcription_text = "Audio processing failed."

    return transcription_text

def load_segment_summary(analysis_dir, segment_num):
    """Load the analysis summary from a previous segment."""
    try:
        files = sorted([f for f in os.listdir(analysis_dir) if f.endswith('_analysis.json')])
        if segment_num > 0 and segment_num <= len(files):
            previous_file = os.path.join(analysis_dir, files[segment_num - 1])
            with open(previous_file, 'r') as f:
                analysis_data = json.load(f)
                return analysis_data.get('summary', '')
    except Exception as ex:
        logger.error(f"Error loading previous summary: {ex}")
    return ''

def execute_video_processing(st, segment_path, system_prompt, user_prompt, temperature, frames_per_second, 
                          analysis_dir, segment_num=0, total_duration=0):
    """Process a video segment, incorporating previous segment context."""
    from utils.analysis import analyze_video
    
    logger.info(f"Processing segment {segment_num + 1} from {segment_path}")
    
    # Create a segment subcontainer to keep each segment's content organized
    segment_subcontainer = st.container()
    
    with segment_subcontainer:
        st.write(f"Processing segment {segment_num + 1}:")
        st.video(segment_path)
    
    # Get the segment timing information
    filename = os.path.basename(segment_path)
    timing = filename.split('_')[-1].replace('.mp4', '')
    start_time, end_time = map(float, timing.split('-'))
    
    with st.spinner(f"Analyzing video segment {segment_num + 1}"):
        # Extract frames
        with st.spinner("Extracting frames..."):
            start_time_proc = time.time()
            
            if st.session_state.config["save_frames"]:
                video_analysis_dir = os.path.dirname(analysis_dir)
                frames_dir = os.path.join(video_analysis_dir, "frames")
                os.makedirs(frames_dir, exist_ok=True)
                logger.debug(f"Using frames directory: {frames_dir}")
                output_dir = frames_dir
            else:
                output_dir = ''
                
            base64frames = process_video(segment_path, frames_per_second, 
                                      resize=st.session_state.config["resize"], output_dir=output_dir)
            logger.info(f"Frame extraction took {(time.time() - start_time_proc):.3f} seconds")
            
        # Get audio transcription if enabled
        if st.session_state.config["audio_transcription"]:
            with st.spinner("Transcribing audio..."):
                start_time_proc = time.time()
                transcription = process_audio(segment_path)
                logger.info(f"Audio transcription took {(time.time() - start_time_proc):.3f} seconds")
        else:
            transcription = ''

        # Load previous segment summary for context
        previous_summary = load_segment_summary(analysis_dir, segment_num)

        # Analyze the segment
        with st.spinner("Analyzing frames..."):
            start_time_proc = time.time()
            analysis = analyze_video(base64frames, system_prompt, user_prompt, transcription, 
                                  previous_summary, start_time, end_time, total_duration, temperature)
            logger.info(f"Analysis took {(time.time() - start_time_proc):.3f} seconds")

    # Show results in the segment subcontainer
    with segment_subcontainer:
        st.success("Segment analysis completed.")
        st.markdown(f"**Analysis**: {analysis}", unsafe_allow_html=True)
        if st.session_state.config["show_transcription"] and st.session_state.config["audio_transcription"] and transcription:
            st.markdown(f"**Transcription**: {transcription}", unsafe_allow_html=True)
    
    # Save analysis results
    analysis_filename = os.path.join(analysis_dir, f"segment_{segment_num+1}_analysis.json")
    analysis_data = {
        "segment": segment_num + 1,
        "start_time": start_time,
        "end_time": end_time,
        "analysis": analysis,
    }
    with open(analysis_filename, 'w') as f:
        json.dump(analysis_data, f, indent=4)
        
    # Store in session state for reference
    from models.session_state import add_analysis
    add_analysis({
        "segment": segment_num + 1,
        "start_time": start_time,
        "end_time": end_time, 
        "analysis": analysis,
        "transcription": transcription if st.session_state.config["audio_transcription"] else None
    })

    # Update session state after each segment is processed
    analyses = load_all_analyses(analysis_dir)
    st.session_state.analyses = analyses
    st.session_state.show_chat = True

    return analysis

def load_all_analyses(analysis_dir):
    """Load all segment analyses for the chat context."""
    analyses = []
    try:
        files = sorted([f for f in os.listdir(analysis_dir) if f.endswith('_analysis.json')])
        for file in files:
            with open(os.path.join(analysis_dir, file), 'r') as f:
                analysis_data = json.load(f)
                analyses.append(analysis_data)
    except Exception as ex:
        logger.error(f"Error loading analyses: {ex}")
    return analyses
