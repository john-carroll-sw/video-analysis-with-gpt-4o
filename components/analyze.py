import streamlit as st
import time
import os
import yt_dlp
from yt_dlp.utils import download_range_func
from utils.video_processing import execute_video_processing

def show_analyze_page():
    """Display the analysis page."""
    
    # Minimal sidebar for this phase
    with st.sidebar:
        st.info("Processing video. You can view the results in the main panel.")
        
        if st.button("Edit Configuration", use_container_width=True):
            st.session_state.current_phase = "Upload"
            st.rerun()
    
    # Main processing container
    st.header("Video Processing & Analysis")
    
    # Check if we need to start processing or if we're showing previous results
    if len(st.session_state.current_analyses) == 0:
        # We need to process the video
        process_container = st.container()
        
        with process_container:
            st.info("Starting video analysis process...")
            
            # Process either file or URL based on what was provided
            if st.session_state.file_or_url == "File" and st.session_state.video_file is not None:
                process_uploaded_file(st.session_state.video_file)
            elif st.session_state.file_or_url == "URL" and st.session_state.video_url != "":
                process_video_url(st.session_state.video_url)
    
    # Display analysis results
    if len(st.session_state.current_analyses) > 0:
        st.subheader("Analysis Results")
        for analysis in st.session_state.current_analyses:
            with st.expander(f"Segment {analysis['segment']} ({analysis['start_time']}-{analysis['end_time']} seconds)", expanded=True):
                st.markdown(f"**Analysis**: {analysis['analysis']}", unsafe_allow_html=True)
                if st.session_state.config["show_transcription"] and "transcription" in analysis and analysis["transcription"]:
                    st.markdown(f"**Transcription**: {analysis['transcription']}", unsafe_allow_html=True)
        
        if st.button("Continue to Chat", type="primary", use_container_width=True):
            st.session_state.current_phase = "Chat"
            st.rerun()

def process_uploaded_file(video_file):
    """Process an uploaded video file."""
    st.write("Processing uploaded file...")
    
    # Create directories
    temp_dir = "temp"
    output_dir = "segments"
    analysis_dir = f"analysis/{time.strftime('%Y%m%d-%H%M%S')}"
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(analysis_dir, exist_ok=True)
    
    # Save uploaded file to temp directory
    video_path = os.path.join(temp_dir, video_file.name)
    with open(video_path, "wb") as f:
        f.write(video_file.getbuffer())
    
    # Split video into segments
    segment_paths = split_video(
        video_path, 
        output_dir, 
        st.session_state.config["shot_interval"]
    )
    
    total_segments = len(segment_paths)
    progress_bar = st.progress(0)
    
    # Process each segment
    for i, segment_path in enumerate(segment_paths):
        # Update progress
        progress_percentage = int((i / total_segments) * 100)
        progress_bar.progress(progress_percentage)
        
        # Process the segment
        execute_video_processing(
            st,
            segment_path,
            st.session_state.config["system_prompt"],
            st.session_state.config["user_prompt"],
            st.session_state.config["temperature"],
            st.session_state.config["frames_per_second"],
            analysis_dir,
            segment_num=i,
            total_duration=total_segments * st.session_state.config["shot_interval"]
        )
        
        # Clean up segment file after processing
        os.remove(segment_path)
    
    # Update progress to 100%
    progress_bar.progress(100)
    st.success("Processing complete!")

def process_video_url(url):
    """Process a video from URL (e.g., YouTube)."""
    st.write(f"Processing video from URL: {url}")
    
    # Create directories
    output_dir = "segments"
    analysis_dir = f"analysis/{time.strftime('%Y%m%d-%H%M%S')}"
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(analysis_dir, exist_ok=True)
    
    # Get video info without downloading
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        video_duration = int(info_dict.get('duration', 0))
    
    # Set segment duration
    segment_duration = st.session_state.config["shot_interval"]
    
    # Use time range if specified
    if st.session_state.config["enable_range"]:
        start_time = st.session_state.config["start_time"]
        end_time = min(st.session_state.config["end_time"], video_duration)
        if end_time == 0:  # If end_time is 0, process until the end
            end_time = video_duration
    else:
        start_time = 0
        end_time = video_duration
    
    # Calculate number of segments
    num_segments = (end_time - start_time) // segment_duration
    if (end_time - start_time) % segment_duration > 0:
        num_segments += 1
    
    progress_bar = st.progress(0)
    segment_paths = []
    
    # Download and process each segment
    for i in range(num_segments):
        seg_start = start_time + (i * segment_duration)
        seg_end = min(seg_start + segment_duration, end_time)
        
        # Update progress for download phase
        progress_percentage = int((i / (num_segments * 2)) * 100)
        progress_bar.progress(progress_percentage)
        
        # Prepare download options for this segment
        filename = f'segments/segment_{seg_start}-{seg_end}.mp4'
        ydl_opts = {
            'format': '(bestvideo[vcodec^=av01]/bestvideo[vcodec^=vp9]/bestvideo)+bestaudio/best',
            'outtmpl': filename,
            'download_ranges': download_range_func(None, [(seg_start, seg_end)]),
            'force_keyframes_at_cuts': True,
            'quiet': True
        }
        
        # Download segment
        with st.spinner(f"Downloading segment {i+1}/{num_segments} ({seg_start}-{seg_end}s)..."):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                segment_paths.append(filename)
            except Exception as e:
                st.error(f"Error downloading segment: {str(e)}")
                continue
    
    # Process each downloaded segment
    for i, segment_path in enumerate(segment_paths):
        # Update progress for processing phase
        progress_percentage = int(((i + num_segments) / (num_segments * 2)) * 100)
        progress_bar.progress(progress_percentage)
        
        # Process segment
        with st.spinner(f"Analyzing segment {i+1}/{len(segment_paths)}..."):
            execute_video_processing(
                st,
                segment_path,
                st.session_state.config["system_prompt"],
                st.session_state.config["user_prompt"],
                st.session_state.config["temperature"],
                st.session_state.config["frames_per_second"],
                analysis_dir,
                segment_num=i,
                total_duration=video_duration
            )
        
        # Clean up segment file
        os.remove(segment_path)
    
    # Update progress to 100%
    progress_bar.progress(100)
    st.success("Processing complete!")

def split_video(video_path, output_dir, segment_length):
    """Split video into segments of specified length."""
    from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
    from moviepy.editor import VideoFileClip
    
    # Get video duration
    clip = VideoFileClip(video_path)
    duration = clip.duration
    clip.close()
    
    segments = []
    for start_time in range(0, int(duration), segment_length):
        end_time = min(start_time + segment_length, duration)
        output_file = os.path.join(
            output_dir, 
            f'{os.path.splitext(os.path.basename(video_path))[0]}_segment_{start_time}-{end_time}.mp4'
        )
        ffmpeg_extract_subclip(video_path, start_time, end_time, targetname=output_file)
        segments.append(output_file)
    
    return segments
