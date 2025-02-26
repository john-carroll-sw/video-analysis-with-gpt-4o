import streamlit as st
import os
from config import SYSTEM_PROMPT, USER_PROMPT

def show_upload_page():
    """Display the upload and configuration page."""
    
    # Show sidebar configuration
    with st.sidebar:
        st.header("Video Configuration")
        
        file_or_url = st.radio("Video source:", ["File", "URL"], index=0 if st.session_state.file_or_url == "File" else 1)
        st.session_state.file_or_url = file_or_url
        
        # Audio options
        st.session_state.config["audio_transcription"] = st.checkbox(
            'Transcribe audio', 
            value=st.session_state.config["audio_transcription"]
        )
        
        if st.session_state.config["audio_transcription"]:
            st.session_state.config["show_transcription"] = st.checkbox(
                'Show transcription', 
                value=st.session_state.config["show_transcription"]
            )
        
        # Video segmentation and processing options
        st.session_state.config["shot_interval"] = int(st.number_input(
            'Shot interval (seconds)', 
            min_value=1, 
            value=int(st.session_state.config["shot_interval"])
        ))
        
        # Fix the frames_per_second input with consistent float types
        st.session_state.config["frames_per_second"] = float(st.number_input(
            'Frames per second', 
            min_value=0.1, 
            max_value=30.0,
            value=float(st.session_state.config["frames_per_second"]), 
            step=0.1,
            format="%.1f"
        ))
        
        st.session_state.config["resize"] = int(st.number_input(
            "Frame resize ratio", 
            min_value=0, 
            value=int(st.session_state.config["resize"])
        ))
        
        st.session_state.config["save_frames"] = st.checkbox(
            'Save frames', 
            value=st.session_state.config["save_frames"]
        )
        
        st.session_state.config["temperature"] = st.slider(
            'Temperature', 
            min_value=0.0, 
            max_value=1.0, 
            value=st.session_state.config["temperature"],
            step=0.1
        )
        
        # AI prompts
        st.session_state.config["system_prompt"] = st.text_area(
            'System Prompt', 
            value=st.session_state.config["system_prompt"],
            height=100
        )
        
        st.session_state.config["user_prompt"] = st.text_area(
            'User Prompt', 
            value=st.session_state.config["user_prompt"]
        )
        
        # Time range options
        st.markdown("---")
        st.subheader("Analysis Range (Optional)")
        
        st.session_state.config["enable_range"] = st.checkbox(
            'Analyze specific time range only', 
            value=st.session_state.config["enable_range"]
        )
        
        if st.session_state.config["enable_range"]:
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.config["start_time"] = st.number_input(
                    'Start time (seconds)', 
                    min_value=0, 
                    value=st.session_state.config["start_time"]
                )
            with col2:
                st.session_state.config["end_time"] = st.number_input(
                    'End time (seconds)', 
                    min_value=0, 
                    value=st.session_state.config["end_time"]
                )
    
    # Main upload container
    st.header("Upload Video")
    
    if file_or_url == "File":
        uploaded_file = st.file_uploader("Upload a video file", type=["mp4", "avi", "mov"])
        if uploaded_file is not None:
            st.session_state.video_file = uploaded_file
            st.session_state.video_url = ""
            st.video(uploaded_file)
            st.success(f"File '{uploaded_file.name}' uploaded successfully!")
    else:
        url = st.text_input("Enter video URL:", "https://www.youtube.com/watch?v=Y6kHpAeIr4c")
        if url != "":
            st.session_state.video_url = url
            st.session_state.video_file = None
            st.video(url)
            st.success("URL entered successfully!")
    
    # Continue button
    if st.session_state.video_file is not None or st.session_state.video_url != "":
        if st.button("Continue to Analysis", type="primary", use_container_width=True):
            st.session_state.current_phase = "Analyze"
            st.rerun()
