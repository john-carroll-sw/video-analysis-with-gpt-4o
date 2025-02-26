import streamlit as st

# Import necessary libraries
import cv2
import os
import time
import json
from dotenv import load_dotenv
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from moviepy.editor import VideoFileClip
from openai import AzureOpenAI
import base64
import yt_dlp
from yt_dlp.utils import download_range_func
import streamlit.components.v1 as components

# Additional imports for chat features
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables and setup API clients
load_dotenv(override=True)

# Default configuration constants
DEFAULT_SHOT_INTERVAL = 10  # In seconds
DEFAULT_FRAMES_PER_SECOND = 1
RESIZE_OF_FRAMES = 4  
DEFAULT_TEMPERATURE = 0.5

# System prompts
SYSTEM_PROMPT = """You are an expert video analyst. You will be shown frames from a video segment. 
Analyze what is happening in detail, considering both visual elements and any provided audio transcription.
If provided with previous segment context, ensure your analysis maintains continuity with what came before."""

USER_PROMPT = "These are the frames from the video segment."

# Initialize session state
if "current_phase" not in st.session_state:
    st.session_state.current_phase = "Upload"
if "video_file" not in st.session_state:
    st.session_state.video_file = None
if "video_url" not in st.session_state:
    st.session_state.video_url = ""
if "file_or_url" not in st.session_state:
    st.session_state.file_or_url = "File"
if "analyses" not in st.session_state:
    st.session_state.analyses = []
if "current_analyses" not in st.session_state:
    st.session_state.current_analyses = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "config" not in st.session_state:
    st.session_state.config = {
        "audio_transcription": True,
        "show_transcription": True,
        "shot_interval": DEFAULT_SHOT_INTERVAL,
        "frames_per_second": float(DEFAULT_FRAMES_PER_SECOND),  # Convert to float
        "resize": RESIZE_OF_FRAMES,
        "save_frames": True,
        "temperature": DEFAULT_TEMPERATURE,
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": USER_PROMPT,
        "enable_range": False,
        "start_time": 0,
        "end_time": 0
    }
if "chat_config" not in st.session_state:
    st.session_state.chat_config = {
        "model": "gpt-4o",
        "temperature": 0.7,
        "summarize_first": False
    }
if "api_config" not in st.session_state:
    st.session_state.api_config = {
        "azure_endpoint": os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        "azure_api_key": os.environ.get("AZURE_OPENAI_API_KEY", ""),
        "azure_api_version": os.environ.get("AZURE_OPENAI_API_VERSION", ""),
        "azure_deployment": os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", ""),
        "whisper_endpoint": os.environ.get("WHISPER_ENDPOINT", ""),
        "whisper_api_key": os.environ.get("WHISPER_API_KEY", ""),
        "whisper_api_version": os.environ.get("WHISPER_API_VERSION", ""),
        "whisper_deployment": os.environ.get("WHISPER_DEPLOYMENT_NAME", "")
    }

# Helper function to validate Azure endpoint
def validate_azure_endpoint(endpoint):
    if not endpoint:
        return False
    if not endpoint.startswith("https://"):
        return False
    if not endpoint.endswith(".openai.azure.com/"):
        # Add trailing slash if missing
        if endpoint.endswith(".openai.azure.com"):
            return endpoint + "/"
    return endpoint

# Configure API clients
aoai_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
aoai_apikey = os.environ["AZURE_OPENAI_API_KEY"]
aoai_apiversion = os.environ["AZURE_OPENAI_API_VERSION"]
aoai_model_name = os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]

# Create AOAI client for answer generation
aoai_client = AzureOpenAI(
    azure_deployment=aoai_model_name,
    api_version=aoai_apiversion,
    azure_endpoint=aoai_endpoint,
    api_key=aoai_apikey
)

# Configure Whisper client
whisper_endpoint = os.environ["WHISPER_ENDPOINT"]
whisper_apikey = os.environ["WHISPER_API_KEY"]
whisper_apiversion = os.environ["WHISPER_API_VERSION"]
whisper_model_name = os.environ["WHISPER_DEPLOYMENT_NAME"]

whisper_client = AzureOpenAI(
    api_version=whisper_apiversion,
    azure_endpoint=whisper_endpoint,
    api_key=whisper_apikey
)

# Main video processing functions
def process_video(video_path, frames_per_second=DEFAULT_FRAMES_PER_SECOND, resize=RESIZE_OF_FRAMES, output_dir=''):
    """Extract and encode frames from a video file."""
    print(f"Starting video processing for {video_path}")
    st.session_state.analyses = None
    st.session_state.show_chat = False

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

        print(f"Processing frame {curr_frame}/{total_frames}")

        if resize != 0:
            height, width, _ = frame.shape
            frame = cv2.resize(frame, (width // resize, height // resize))

        _, buffer = cv2.imencode(".jpg", frame)

        if output_dir:
            frame_filename = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(video_path))[0]}_frame_{frame_count}.jpg")
            with open(frame_filename, "wb") as f:
                f.write(buffer)
                print(f"Saved frame: {frame_filename}")
            frame_count += 1

        base64Frames.append(base64.b64encode(buffer).decode("utf-8"))
        curr_frame += frames_to_skip
    video.release()
    
    return base64Frames

def process_audio(video_path):
    """Extract and transcribe audio from a video file."""
    print(f"Starting audio transcription for {video_path}")
    transcription_text = ''
    
    try:
        # First check if the video file exists and has audio
        clip = VideoFileClip(video_path)
        if not clip.audio:
            print(f"No audio track found in {video_path}")
            clip.close()
            return "No audio found in this segment."

        # Extract audio to file in the same directory as the video
        base_video_path, _ = os.path.splitext(video_path)
        audio_path = f"{base_video_path}.mp3"
        
        try:
            clip.audio.write_audiofile(audio_path, bitrate="32k", verbose=False, logger=None)
            clip.audio.close()
            clip.close()
            print(f"Extracted audio to {audio_path}")

            # Transcribe the audio
            with open(audio_path, "rb") as audio_file:
                transcription = whisper_client.audio.transcriptions.create(
                    model=whisper_model_name,
                    file=audio_file
                )
                transcription_text = transcription.text
                print(f"Transcription successful: {transcription_text}")
                print(f"Audio file saved at: {audio_path}")

        except Exception as ex:
            print(f'ERROR in audio processing: {str(ex)}')
            if os.path.exists(audio_path):
                os.remove(audio_path)  # Only remove on error
            
    except Exception as ex:
        print(f'ERROR processing audio: {str(ex)}')
        transcription_text = "Audio processing failed."

    return transcription_text

def analyze_video(base64frames, system_prompt, user_prompt, transcription, previous_summary, start_time, end_time, total_duration, temperature):
    """Analyze video frames with GPT-4o Vision, incorporating context from previous segments."""
    try:
        # Construct content array with frames
        content = [
            *map(lambda x: {
                "type": "image_url",
                "image_url": {"url": f'data:image/jpg;base64,{x}', "detail": "auto"}
            }, base64frames)
        ]

        # Add segment context and transcription if available
        segment_context = f"\nAnalyzing segment from {start_time} to {end_time} seconds of a {total_duration} second video."
        if previous_summary:
            segment_context += f"\nPrevious segment summary: {previous_summary}"
        if transcription:
            segment_context += f"\nAudio transcription: {transcription}"

        content.append({"type": "text", "text": segment_context})

        response = aoai_client.chat.completions.create(
            model=aoai_model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "user", "content": content}
            ],
            temperature=temperature,
            max_tokens=4096
        )

        json_response = json.loads(response.model_dump_json())
        return json_response['choices'][0]['message']['content']

    except Exception as ex:
        print(f'ERROR: {ex}')
        return f'ERROR: {ex}'

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
        print(f"Error loading previous summary: {ex}")
    return ''

def execute_video_processing(st, segment_path, system_prompt, user_prompt, temperature, frames_per_second, 
                           analysis_dir, segment_num=0, total_duration=0):
    """Process a video segment, incorporating previous segment context."""
    
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
                print(f"Created frames directory at: {frames_dir}")
                output_dir = frames_dir
            else:
                output_dir = ''
                
            base64frames = process_video(segment_path, frames_per_second, resize=st.session_state.config["resize"], output_dir=output_dir)
            print(f"Frame extraction took {(time.time() - start_time_proc):.3f} seconds")
            
        # Get audio transcription if enabled
        if st.session_state.config["audio_transcription"]:
            with st.spinner("Transcribing audio..."):
                start_time_proc = time.time()
                transcription = process_audio(segment_path)
                print(f"Audio transcription took {(time.time() - start_time_proc):.3f} seconds")
        else:
            transcription = ''

        # Load previous segment summary for context
        previous_summary = load_segment_summary(analysis_dir, segment_num)

        # Analyze the segment
        with st.spinner("Analyzing frames..."):
            start_time_proc = time.time()
            analysis = analyze_video(base64frames, system_prompt, user_prompt, transcription, 
                                  previous_summary, start_time, end_time, total_duration, temperature)
            print(f"Analysis took {(time.time() - start_time_proc):.3f} seconds")

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
        "summary": analysis[:500]  # Create a shorter summary for context
    }
    with open(analysis_filename, 'w') as f:
        json.dump(analysis_data, f, indent=4)
        
    # Store in session state for reference
    st.session_state.current_analyses.append({
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
        print(f"Error loading analyses: {ex}")
    return analyses

def chat_with_video_analysis(query, analyses, chat_history=None, temperature=0.7, summarize_first=False):
    """Use GPT-4o to answer questions about the video using the collected analyses."""
    try:
        # Construct context from analyses
        context = "Video Analysis Context:\n\n"
        
        if summarize_first and len(analyses) > 1:
            # First create a summary of all segments to provide a high-level overview
            summary_prompt = "Summarize the following video analysis segments into a coherent overview:\n\n"
            for analysis in analyses:
                summary_prompt += f"Segment {analysis['segment']} ({analysis['start_time']}-{analysis['end_time']} seconds):\n"
                summary_prompt += f"{analysis['analysis'][:500]}...\n\n"
                
            summary_response = aoai_client.chat.completions.create(
                model=aoai_model_name,
                messages=[
                    {"role": "system", "content": "Create a concise summary of the video based on these segment analyses."},
                    {"role": "user", "content": summary_prompt}
                ],
                temperature=temperature,
                max_tokens=500
            )
            
            context += "Overall Summary:\n" + json.loads(summary_response.model_dump_json())['choices'][0]['message']['content'] + "\n\n"

        # Add individual segment analyses
        for analysis in analyses:
            context += f"Segment {analysis['segment']} ({analysis['start_time']}-{analysis['end_time']} seconds):\n"
            context += f"{analysis['analysis']}\n\n"

        # Construct messages array with chat history
        messages = [
            {"role": "system", "content": "You are an assistant that answers questions about a video based on its analysis. Use the provided analysis context to give accurate and relevant answers. Maintain context from the ongoing conversation."},
            {"role": "user", "content": f"Here is the video analysis to reference:\n{context}"}
        ]

        # Add chat history if it exists
        if chat_history:
            messages.extend(chat_history)

        # Add current query
        messages.append({"role": "user", "content": query})

        # Return streaming response
        response = aoai_client.chat.completions.create(
            model=aoai_model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=1000,
            stream=True
        )
        
        return response

    except Exception as ex:
        print(f'Chat error: {ex}')
        return f'Error generating response: {ex}'

# Header and navigation tabs
st.image("microsoft.png", width=100)
st.title('Video Analysis with Azure OpenAI')

# Define tab titles and corresponding phases
tabs = [
    ("Upload & Configure", "Upload"),
    ("Process & Analyze", "Analyze"),
    ("Chat & Insights", "Chat")
]

# Create custom tabs using columns and buttons
cols = st.columns(len(tabs))

for i, (label, phase) in enumerate(tabs):
    with cols[i]:
        # Style active tab differently
        button_type = "primary" if st.session_state.current_phase == phase else "secondary"
        # Disable buttons based on phase conditions
        disabled = False
        # if phase == "Analyze":
        #     disabled = st.session_state.video_file is None and st.session_state.video_url == ""
        # if phase == "Chat":
        #     disabled = len(st.session_state.analyses) == 0
        # Render full-width button that looks like a tab
        if st.button(label, key=f"tab_{i}", type=button_type, disabled=disabled, use_container_width=True):
            st.session_state.current_phase = phase
            st.rerun()

st.divider()  # Separator below tabs

# PHASE 1: UPLOAD & CONFIGURE
if st.session_state.current_phase == "Upload":
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
            max_value=30.0,  # Add max_value to ensure all params are float
            value=float(st.session_state.config["frames_per_second"]), 
            step=0.1,
            format="%.1f"  # Format as float with 1 decimal place
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

# PHASE 2: PROCESS & ANALYZE
elif st.session_state.current_phase == "Analyze":
    # Minimal or no sidebar for this phase
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
                # Process file
                # (Your existing file processing code would go here)
                st.write("Processing uploaded file...")
                
                # Mock example code (replace with actual implementation):
                progress_bar = st.progress(0)
                for i in range(100):
                    time.sleep(0.05)
                    progress_bar.progress(i + 1)
                
                # Simulate adding analysis results
                st.session_state.current_analyses = [
                    {
                        "segment": 1,
                        "start_time": 0,
                        "end_time": 10,
                        "analysis": "This is a sample analysis of the first segment.",
                        "transcription": "Sample transcription for segment 1."
                    },
                    {
                        "segment": 2,
                        "start_time": 10,
                        "end_time": 20,
                        "analysis": "This is a sample analysis of the second segment.",
                        "transcription": "Sample transcription for segment 2."
                    }
                ]
                
                st.session_state.analyses = st.session_state.current_analyses
                
            elif st.session_state.file_or_url == "URL" and st.session_state.video_url != "":
                # Process URL
                # (Your existing URL processing code would go here)
                st.write(f"Processing video from URL: {st.session_state.video_url}")
                
                # Mock example code (replace with actual implementation):
                progress_bar = st.progress(0)
                for i in range(100):
                    time.sleep(0.05)
                    progress_bar.progress(i + 1)
                
                # Simulate adding analysis results
                st.session_state.current_analyses = [
                    {
                        "segment": 1,
                        "start_time": 0,
                        "end_time": 10,
                        "analysis": "This is a sample analysis of the first segment from URL.",
                        "transcription": "Sample transcription for segment 1 from URL."
                    },
                    {
                        "segment": 2,
                        "start_time": 10,
                        "end_time": 20,
                        "analysis": "This is a sample analysis of the second segment from URL.",
                        "transcription": "Sample transcription for segment 2 from URL."
                    }
                ]
                
                st.session_state.analyses = st.session_state.current_analyses
            
            st.success("Processing complete!")
    
    # Display analysis results
    if len(st.session_state.current_analyses) > 0:
        st.subheader("Analysis Results")
        for analysis in st.session_state.current_analyses:
            with st.expander(f"Segment {analysis['segment']} ({analysis['start_time']}-{analysis['end_time']} seconds)", expanded=True):
                st.markdown(f"**Analysis**: {analysis['analysis']}", unsafe_allow_html=True)
                if st.session_state.config["show_transcription"] and "transcription" in analysis:
                    st.markdown(f"**Transcription**: {analysis['transcription']}", unsafe_allow_html=True)
        
        if st.button("Continue to Chat", type="primary", use_container_width=True):
            st.session_state.current_phase = "Chat"
            st.rerun()

# PHASE 3: CHAT & INSIGHTS
elif st.session_state.current_phase == "Chat":
    # Chat configuration sidebar (inspired by Chatbot.py)
    with st.sidebar:
        st.title("Chat Settings")
        
        # Model selection (limited to models that can understand the analysis)
        model_options = ["gpt-4o", "gpt-4"]
        selected_model = st.selectbox(
            "Model",
            options=model_options,
            index=model_options.index(st.session_state.chat_config.get("model", "gpt-4o")) if st.session_state.chat_config.get("model") in model_options else 0
        )
        st.session_state.chat_config["model"] = selected_model
        
        # Temperature slider with info tooltip
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.chat_config.get("temperature", 0.7),
            step=0.1,
            help="Higher values make output more random, lower values more deterministic"
        )
        st.session_state.chat_config["temperature"] = temperature
        
        # Context handling options
        st.subheader("Context Settings")
        
        st.session_state.chat_config["summarize_first"] = st.checkbox(
            "Generate summary first",
            value=st.session_state.chat_config.get("summarize_first", True),
            help="Create a high-level summary of all segments before answering questions"
        )
        
        st.session_state.chat_config["include_transcription"] = st.checkbox(
            "Include transcriptions in context",
            value=st.session_state.chat_config.get("include_transcription", True),
            help="Include audio transcriptions as part of the analysis context"
        )
        
        max_context = st.slider(
            "Max context length (segments)",
            min_value=1,
            max_value=len(st.session_state.analyses) if st.session_state.analyses else 5,
            value=st.session_state.chat_config.get("max_context", len(st.session_state.analyses) if st.session_state.analyses else 5),
            help="Maximum number of analysis segments to include in context"
        )
        st.session_state.chat_config["max_context"] = max_context
        
        # Action buttons
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Clear Chat History", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
        with col2:
            if st.button("Return to Analysis", use_container_width=True):
                st.session_state.current_phase = "Analyze" 
                st.rerun()
        
        st.markdown("---")
        expert_mode = st.toggle(
            "Advanced Options", 
            value=st.session_state.chat_config.get("expert_mode", False),
            help="Show advanced options and technical details"
        )
        st.session_state.chat_config["expert_mode"] = expert_mode
        
        # Show additional expert options if enabled
        if expert_mode:
            # System prompt customization
            system_prompt = st.text_area(
                "System Prompt",
                value=st.session_state.chat_config.get("system_prompt", "You are an assistant that answers questions about a video based on its analysis. Use the provided analysis context to give accurate and relevant answers. Maintain context from the ongoing conversation."),
                height=100
            )
            st.session_state.chat_config["system_prompt"] = system_prompt
            
            # Model parameters
            st.session_state.chat_config["max_tokens"] = st.number_input(
                "Max Response Tokens",
                min_value=100,
                max_value=4096,
                value=st.session_state.chat_config.get("max_tokens", 1000),
                step=50
            )
            
            # API Configuration Section
            st.subheader("API Configuration")
            
            # OpenAI API Configuration Section
            with st.expander("Azure OpenAI API Settings", expanded=False):
                # Azure OpenAI settings
                azure_api_key = st.text_input(
                    "Azure OpenAI API Key", 
                    type="password",
                    value=st.session_state.api_config["azure_api_key"],
                    placeholder="your-azure-openai-api-key"
                )
                st.session_state.api_config["azure_api_key"] = azure_api_key
                
                azure_endpoint = st.text_input(
                    "Azure OpenAI Endpoint", 
                    value=st.session_state.api_config["azure_endpoint"],
                    placeholder="https://your-azure-openai-endpoint.openai.azure.com/"
                )
                st.session_state.api_config["azure_endpoint"] = azure_endpoint
                
                azure_deployment = st.text_input(
                    "Azure Deployment Name", 
                    value=st.session_state.api_config["azure_deployment"],
                    placeholder="gpt-4o",
                    help="This is your deployment name, e.g., gpt-4o"
                )
                st.session_state.api_config["azure_deployment"] = azure_deployment
                
                azure_api_version = st.text_input(
                    "Azure API Version", 
                    value=st.session_state.api_config["azure_api_version"],
                    placeholder="2024-08-01-preview"
                )
                st.session_state.api_config["azure_api_version"] = azure_api_version
                
                st.markdown("[Get Azure OpenAI access](https://azure.microsoft.com/en-us/products/cognitive-services/openai-service)")
            
            # Whisper API Configuration Section
            with st.expander("Azure Whisper API Settings", expanded=False):
                # Whisper settings
                whisper_api_key = st.text_input(
                    "Whisper API Key", 
                    type="password",
                    value=st.session_state.api_config["whisper_api_key"],
                    placeholder="your-whisper-api-key"
                )
                st.session_state.api_config["whisper_api_key"] = whisper_api_key
                
                whisper_endpoint = st.text_input(
                    "Whisper Endpoint", 
                    value=st.session_state.api_config["whisper_endpoint"],
                    placeholder="https://your-whisper-endpoint.openai.azure.com/"
                )
                st.session_state.api_config["whisper_endpoint"] = whisper_endpoint
                
                whisper_deployment = st.text_input(
                    "Whisper Deployment Name", 
                    value=st.session_state.api_config["whisper_deployment"],
                    placeholder="whisper",
                    help="This is your whisper deployment name"
                )
                st.session_state.api_config["whisper_deployment"] = whisper_deployment
                
                whisper_api_version = st.text_input(
                    "Whisper API Version", 
                    value=st.session_state.api_config["whisper_api_version"],
                    placeholder="2023-09-01-preview"
                )
                st.session_state.api_config["whisper_api_version"] = whisper_api_version
            
            # Apply Changes button
            if st.button("Apply API Changes", use_container_width=True):
                
                # Get values from session state
                azure_endpoint = st.session_state.api_config["azure_endpoint"]
                azure_api_key = st.session_state.api_config["azure_api_key"]
                azure_deployment = st.session_state.api_config["azure_deployment"]
                azure_api_version = st.session_state.api_config["azure_api_version"]
                
                whisper_endpoint = st.session_state.api_config["whisper_endpoint"]
                whisper_api_key = st.session_state.api_config["whisper_api_key"]
                whisper_deployment = st.session_state.api_config["whisper_deployment"]
                whisper_api_version = st.session_state.api_config["whisper_api_version"]
                
                # Validate endpoints
                valid_azure = validate_azure_endpoint(azure_endpoint)
                valid_whisper = validate_azure_endpoint(whisper_endpoint)
                
                if not valid_azure:
                    st.error("Invalid Azure OpenAI endpoint format. Should be: https://YOUR_RESOURCE_NAME.openai.azure.com/")
                if not valid_whisper:
                    st.error("Invalid Whisper endpoint format. Should be: https://YOUR_RESOURCE_NAME.openai.azure.com/")
                
                if valid_azure and azure_api_key and azure_deployment and azure_api_version:
                    # Update the Azure OpenAI client
                    try:
                        aoai_client = AzureOpenAI(
                            azure_deployment=azure_deployment,
                            api_version=azure_api_version,
                            azure_endpoint=azure_endpoint,
                            api_key=azure_api_key
                        )
                        st.success("Azure OpenAI API settings updated!")
                    except Exception as e:
                        st.error(f"Failed to update Azure OpenAI client: {str(e)}")
                
                if valid_whisper and whisper_api_key and whisper_deployment and whisper_api_version:
                    # Update the Whisper client
                    try:
                        whisper_client = AzureOpenAI(
                            api_version=whisper_api_version,
                            azure_endpoint=whisper_endpoint,
                            api_key=whisper_api_key
                        )
                        st.success("Whisper API settings updated!")
                    except Exception as e:
                        st.error(f"Failed to update Whisper client: {str(e)}")
            
            # Debug button to check environment variables
            if st.button("Debug API Settings", use_container_width=True):
                st.write("Current API Configuration:")
                for key, value in st.session_state.api_config.items():
                    if value and "api_key" in key:
                        # Mask API keys for security
                        masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
                        st.write(f"{key}: {masked}")
                    else:
                        st.write(f"{key}: {value}")
            
            # Debug information
            if st.checkbox("Show Context Statistics", value=False):
                st.subheader("Context Statistics")
                
                # Count total tokens in context
                max_context = st.session_state.chat_config.get("max_context", len(st.session_state.analyses))
                context_size = sum(len(analysis.get("analysis", "").split()) for analysis in st.session_state.analyses[:max_context])
                st.write(f"Analysis segments: {len(st.session_state.analyses[:max_context])}")
                st.write(f"Approximate context size: ~{context_size} words")
                
                # Show most recent chat history entries
                if st.session_state.chat_history:
                    st.write(f"Chat history entries: {len(st.session_state.chat_history)}")
                    if len(st.session_state.chat_history) > 0:
                        last_msg = next((m for m in reversed(st.session_state.chat_history) if m["role"] == "user"), None)
                        if last_msg:
                            st.write(f"Latest user query: '{last_msg['content'][:50]}...' ({len(last_msg['content'].split())} words)")
    
    # Main chat container
    st.header("💬 Chat about the video analysis")
    
    # # Video analysis summary for reference (collapsed by default)
    # with st.expander("Video Analysis Summary", expanded=False):
    #     if len(st.session_state.analyses) > 0:
    #         for analysis in st.session_state.analyses:
    #             st.markdown(f"**Segment {analysis['segment']} ({analysis['start_time']}-{analysis['end_time']} seconds)**")
    #             st.markdown(analysis['analysis'][:300] + "..." if len(analysis['analysis']) > 300 else analysis['analysis'])
    #             st.markdown("---")
    #     else:
    #         st.info("No analysis data available.")
    
    # Chat interface with fixed scrolling region
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    
    # Messages area (scrollable)
    st.markdown('<div class="messages-container">', unsafe_allow_html=True)
    
    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            
    st.markdown('</div>', unsafe_allow_html=True)  # Close messages container
    
    # Chat input area (fixed at bottom)
    st.markdown('<div class="chat-input-container">', unsafe_allow_html=True)
    
    # Chat input with prompt
    placeholder_text = "Ask a question about the video analysis..."
    prompt = st.chat_input(placeholder_text)
    
    if prompt:
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            # Get settings from session state
            temperature = st.session_state.chat_config.get("temperature", 0.7)
            summarize_first = st.session_state.chat_config.get("summarize_first", False)
            include_transcription = st.session_state.chat_config.get("include_transcription", True)
            max_context = st.session_state.chat_config.get("max_context", len(st.session_state.analyses))
            system_prompt = st.session_state.chat_config.get("system_prompt", 
                "You are an assistant that answers questions about a video based on its analysis. Use the provided analysis context to give accurate and relevant answers. Maintain context from the ongoing conversation.")
            max_tokens = st.session_state.chat_config.get("max_tokens", 1000)
            
            # Make sure clients are properly initialized before use
            if 'aoai_client' not in globals() or aoai_client is None:
                error_msg = "Azure OpenAI client is not properly configured. Please check API settings."
                message_placeholder.error(error_msg)
                logger.error("Azure OpenAI client is not initialized")
                full_response = error_msg
            else:
                try:
                    # Limit context to max_context segments
                    limited_analyses = st.session_state.analyses[:max_context] if max_context < len(st.session_state.analyses) else st.session_state.analyses
                    
                    # Construct context from analyses
                    context = "Video Analysis Context:\n\n"
                    
                    # Generate summary if enabled and multiple segments
                    if summarize_first and len(limited_analyses) > 1:
                        summary_prompt = "Summarize the following video analysis segments into a coherent overview:\n\n"
                        for analysis in limited_analyses:
                            summary_prompt += f"Segment {analysis['segment']} ({analysis['start_time']}-{analysis['end_time']} seconds):\n"
                            summary_prompt += f"{analysis['analysis'][:500]}...\n\n"
                            
                        summary_response = aoai_client.chat.completions.create(
                            model=aoai_model_name,
                            messages=[
                                {"role": "system", "content": "Create a concise summary of the video based on these segment analyses."},
                                {"role": "user", "content": summary_prompt}
                            ],
                            temperature=temperature,
                            max_tokens=500
                        )
                        
                        context += "Overall Summary:\n" + json.loads(summary_response.model_dump_json())['choices'][0]['message']['content'] + "\n\n"

                    # Add individual segment analyses
                    for analysis in limited_analyses:
                        context += f"Segment {analysis['segment']} ({analysis['start_time']}-{analysis['end_time']} seconds):\n"
                        context += f"{analysis['analysis']}\n\n"
                        
                        # Include transcriptions if enabled and available
                        if include_transcription and "transcription" in analysis and analysis["transcription"]:
                            context += f"Transcription for segment {analysis['segment']}: {analysis['transcription']}\n\n"

                    # Construct messages array with system prompt, context, and chat history
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Here is the video analysis to reference:\n{context}"}
                    ]

                    # Add chat history if it exists
                    if len(st.session_state.chat_history) > 0:
                        # Convert to the format expected by the API
                        api_messages = []
                        for msg in st.session_state.chat_history:
                            if msg["role"] in ["user", "assistant"]:
                                api_messages.append({"role": msg["role"], "content": msg["content"]})
                        messages.extend(api_messages)

                    # Add current query
                    messages.append({"role": "user", "content": prompt})
                    
                    # Get streaming response
                    for chunk in aoai_client.chat.completions.create(
                        model=aoai_model_name,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=True
                    ):
                        if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content is not None:
                            full_response += chunk.choices[0].delta.content
                            message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                except Exception as e:
                    error_msg = f"Error generating response: {str(e)}"
                    message_placeholder.error(error_msg)
                    full_response = error_msg
                    logger.error(f"Chat error: {str(e)}")
            
        # Update chat history
        st.session_state.chat_history.extend([
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": full_response}
        ])
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close input container
