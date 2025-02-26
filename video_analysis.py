import streamlit as st
# Set page config as the very first Streamlit command
st.set_page_config(
    page_title="Video Analysis with GPT-4o",
    layout="wide",
    initial_sidebar_state="auto",
)

# Now continue with other imports
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

# Default configuration
DEFAULT_SHOT_INTERVAL = 10  # In seconds
DEFAULT_FRAMES_PER_SECOND = 1
RESIZE_OF_FRAMES = 4  # Changed default resize ratio to 4
DEFAULT_TEMPERATURE = 0.5

# System prompts
SYSTEM_PROMPT = """You are an expert video analyst. You will be shown frames from a video segment. 
Analyze what is happening in detail, considering both visual elements and any provided audio transcription.
If provided with previous segment context, ensure your analysis maintains continuity with what came before."""

USER_PROMPT = "These are the frames from the video segment."

# Load configuration
load_dotenv(override=True)

# Configuration of OpenAI GPT-4o
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

# Configuration of Whisper
whisper_endpoint = os.environ["WHISPER_ENDPOINT"]
whisper_apikey = os.environ["WHISPER_API_KEY"]
whisper_apiversion = os.environ["WHISPER_API_VERSION"]
whisper_model_name = os.environ["WHISPER_DEPLOYMENT_NAME"]

# Create AOAI client for whisper
whisper_client = AzureOpenAI(
    api_version=whisper_apiversion,
    azure_endpoint=whisper_endpoint,
    api_key=whisper_apikey
)

# Initialize session state for chat
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "analyses" not in st.session_state:
    st.session_state.analyses = []
if "show_chat" not in st.session_state:
    st.session_state.show_chat = False
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = []

# Add sidebar state to session state
if "sidebar_collapsed" not in st.session_state:
    st.session_state.sidebar_collapsed = False

# Add custom CSS for the chat container
st.markdown("""
<style>
    /* Chat container styling */
    .chat-container {
        display: flex;
        flex-direction: column;
        height: 500px;
        border: 1px solid #ddd;
        border-radius: 8px;
        overflow: hidden;
    }
    .messages-container {
        flex-grow: 1;
        overflow-y: auto;
        padding: 15px;
    }
    .chat-input-container {
        padding: 10px;
        border-top: 1px solid #ddd;
        background-color: #f9f9f9;
    }

    /* Hide sidebar toggle button when needed */
    .sidebar-collapsed-hide {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

# JavaScript to toggle sidebar state
def toggle_sidebar():
    components.html(
        """
        <script>
        // Select the sidebar toggle button
        const toggle = parent.document.querySelector('[data-testid="collapsedControl"]');
        if (toggle) {
            // Simulate click to hide sidebar
            toggle.click();
        }
        </script>
        """,
        height=0,
    )

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
            
            if save_frames:
                video_analysis_dir = os.path.dirname(analysis_dir)
                frames_dir = os.path.join(video_analysis_dir, "frames")
                os.makedirs(frames_dir, exist_ok=True)
                print(f"Created frames directory at: {frames_dir}")
                output_dir = frames_dir
            else:
                output_dir = ''
                
            base64frames = process_video(segment_path, frames_per_second, resize=resize, output_dir=output_dir)
            print(f"Frame extraction took {(time.time() - start_time_proc):.3f} seconds")
            
        # Get audio transcription if enabled
        if audio_transcription:
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
        if show_transcription and audio_transcription and transcription:
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
        "transcription": transcription if audio_transcription else None
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

def chat_with_video_analysis(query, analyses, chat_history=None, temperature=0.7):
    """Use GPT-4o to answer questions about the video using the collected analyses and chat history."""
    try:
        # Construct context from analyses
        context = "Video Analysis Context:\n\n"
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

        # Change to use streaming response
        response = aoai_client.chat.completions.create(
            model=aoai_model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=1000,
            stream=True  # Enable streaming
        )
        
        # Return the stream object instead of processed response
        return response

    except Exception as ex:
        print(f'Chat error: {ex}')
        return f'Error generating response: {ex}'

# Streamlit UI Setup
st.image("microsoft.png", width=100)
st.title('Video Analysis with GPT-4o')

# Create three containers for different phases of the application
upload_container = st.container()    # Step 1: Video configuration and upload
analysis_container = st.container()  # Step 2: Video processing and analysis 
chat_container = st.container()      # Step 3: Chat interface

# Initialize session states
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "analyses" not in st.session_state:
    st.session_state.analyses = []
if "show_chat" not in st.session_state:
    st.session_state.show_chat = False
if "current_analyses" not in st.session_state:
    st.session_state.current_analyses = []
if "displayed_analyses" not in st.session_state:
    st.session_state.displayed_analyses = False

# STEP 1: VIDEO UPLOAD & CONFIGURATION
with upload_container:
    st.header("Step 1: Video Upload & Configuration")
    
    # Create sidebar for configuration settings
    with st.sidebar:
        st.header("Configuration")
        file_or_url = st.selectbox("Video source:", ["File", "URL"], index=0)
        
        audio_transcription = st.checkbox('Transcribe audio', True)
        if audio_transcription:
            show_transcription = st.checkbox('Show transcription', True)
            
        shot_interval = st.number_input('Shot interval (seconds)', min_value=1, value=DEFAULT_SHOT_INTERVAL)
        frames_per_second = st.number_input('Frames per second', value=DEFAULT_FRAMES_PER_SECOND)
        resize = st.number_input("Frame resize ratio", min_value=0, value=RESIZE_OF_FRAMES)
        save_frames = st.checkbox('Save frames', True)
        temperature = st.number_input('Temperature', value=DEFAULT_TEMPERATURE)
        system_prompt = st.text_area('System Prompt', SYSTEM_PROMPT)
        user_prompt = st.text_area('User Prompt', USER_PROMPT)
        
        st.markdown("---")
        st.subheader("Analysis Range (Optional)")
        enable_range = st.checkbox('Analyze specific time range only', False)
        if enable_range:
            col1, col2 = st.columns(2)
            with col1:
                start_time = st.number_input('Start time (seconds)', min_value=0, value=0)
            with col2:
                end_time = st.number_input('End time (seconds)', min_value=0, value=0)
    
    # Main upload area
    col1, col2 = st.columns([3, 1])
    with col1:
        if file_or_url == "File":
            video_file = st.file_uploader("Upload a video file", type=["mp4", "avi", "mov"])
        else:
            url = st.text_area("Enter video URL:", "https://www.youtube.com/watch?v=Y6kHpAeIr4c")
    
    with col2:
        analyze_button = st.button("Analyze Video", use_container_width=True, type='primary')

# STEP 2: VIDEO PROCESSING & ANALYSIS
with analysis_container:
    st.header("Step 2: Video Processing & Analysis")
    
    # Always show previously processed analyses to keep them visible
    if st.session_state.current_analyses:
        for analysis_data in st.session_state.current_analyses:
            with st.expander(f"Segment {analysis_data['segment']} ({analysis_data['start_time']}-{analysis_data['end_time']} seconds)", expanded=True):
                st.markdown(f"**Analysis**: {analysis_data['analysis']}", unsafe_allow_html=True)
                if analysis_data.get('transcription') and show_transcription:
                    st.markdown(f"**Transcription**: {analysis_data['transcription']}", unsafe_allow_html=True)
    
    # Process video when analyze button is clicked
    if analyze_button:
        # Collapse sidebar after analysis starts
        if not st.session_state.sidebar_collapsed:
            toggle_sidebar()
            st.session_state.sidebar_collapsed = True
        
        # Clear previous analyses
        st.session_state.current_analyses = []
        st.session_state.displayed_analyses = False
        
        if file_or_url == "URL":
            video_title = "video"  # Will be set from URL info
            try:
                # Setup youtube-dl options
                ydl_opts = {
                    'format': '(bestvideo[vcodec^=av01]/bestvideo[vcodec^=vp9]/bestvideo)+bestaudio/best',
                    'force_keyframes_at_cuts': True
                }
                
                # Get video info
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=False)
                    video_title = info_dict.get('title', 'video')
                    video_duration = int(info_dict.get('duration', 0))

                # Create directory structure
                video_base_dir = 'video'
                os.makedirs(video_base_dir, exist_ok=True)
                
                analysis_dir = f"{video_title}_analysis"
                video_dir = os.path.join(video_base_dir, analysis_dir)
                shots_dir = os.path.join(video_dir, "shots")
                analysis_subdir = os.path.join(video_dir, "analysis")
                os.makedirs(shots_dir, exist_ok=True)
                os.makedirs(analysis_subdir, exist_ok=True)

                # Add range validation after getting video duration
                if enable_range:
                    if end_time == 0:
                        end_time = video_duration
                    if end_time > video_duration:
                        st.warning(f"End time exceeds video duration. Setting to maximum ({video_duration} seconds)")
                        end_time = video_duration
                    if start_time >= end_time:
                        st.error("Start time must be less than end time")
                        st.stop()
                    video_duration = end_time - start_time

                # Download and process video in segments
                segment_num = 0
                for start in range(start_time if enable_range else 0, 
                                  end_time if enable_range else video_duration, 
                                  shot_interval):
                    end = min(start + shot_interval, video_duration)
                    shot_path = os.path.join(shots_dir, f'shot_{start}-{end}.mp4')
                    
                    # Download segment
                    with st.spinner(f"Downloading segment {start}-{end} seconds..."):
                        ydl_opts['download_ranges'] = download_range_func(None, [(start, end)])
                        ydl_opts['outtmpl'] = shot_path
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([url])

                    # Process segment
                    analysis = execute_video_processing(
                        st, shot_path, system_prompt, user_prompt, temperature,
                        frames_per_second, analysis_subdir, segment_num, video_duration
                    )
                    st.markdown(f"**Analysis**: {analysis}", unsafe_allow_html=True)
                    
                    os.remove(shot_path)  # Clean up segment file
                    segment_num += 1

                # After all segments are processed, enable chat
                analyses = load_all_analyses(analysis_subdir)
                st.session_state.analyses = analyses
                st.session_state.show_chat = True

            except Exception as ex:
                st.error(f"Error processing URL: {str(ex)}")

        else:  # File upload processing
            if video_file is not None:
                try:
                    video_title = os.path.splitext(video_file.name)[0]
                    video_base_dir = 'video'
                    os.makedirs(video_base_dir, exist_ok=True)
                    
                    # Create analysis directory structure
                    analysis_dir = f"{video_title}_analysis"
                    video_dir = os.path.join(video_base_dir, analysis_dir)
                    
                    # Create subdirectories within video_title_analysis
                    segments_dir = os.path.join(video_dir, "segments")
                    analysis_subdir = os.path.join(video_dir, "analysis")
                    frames_dir = os.path.join(video_dir, "frames")  # Moved frames inside video_title_analysis
                    
                    # Create all necessary directories
                    for dir_path in [video_dir, segments_dir, analysis_subdir, frames_dir]:
                        os.makedirs(dir_path, exist_ok=True)
                        print(f"Created directory: {dir_path}")

                    # Save uploaded file in video_dir
                    video_path = os.path.join(video_dir, video_file.name)
                    with open(video_path, "wb") as f:
                        f.write(video_file.getbuffer())
                    print(f"Saved video file to: {video_path}")

                    # Get video duration
                    cap = cv2.VideoCapture(video_path)
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    video_duration = total_frames / fps
                    cap.release()

                    # Add range validation after getting video duration
                    if enable_range:
                        if end_time == 0:
                            end_time = video_duration
                        if end_time > video_duration:
                            st.warning(f"End time exceeds video duration. Setting to maximum ({video_duration:.1f} seconds)")
                            end_time = video_duration
                        if start_time >= end_time:
                            st.error("Start time must be less than end time")
                            st.stop()
                        video_duration = end_time - start_time

                    # Process video in segments
                    segment_num = 0
                    for start_time_seg in range(int(start_time if enable_range else 0), 
                                               int(end_time if enable_range else video_duration), 
                                               shot_interval):
                        end_time_seg = min(start_time_seg + shot_interval, 
                                          end_time if enable_range else video_duration)
                        segment_path = os.path.join(segments_dir, f'segment_{start_time_seg}-{end_time_seg}.mp4')  # Changed from shot_path
                        print(f"Creating segment: {segment_path}")
                        
                        # Extract segment
                        try:
                            ffmpeg_extract_subclip(video_path, start_time_seg, end_time_seg, targetname=segment_path)
                            print(f"Successfully created segment: {segment_path}")
                            
                            if not os.path.exists(segment_path):
                                raise FileNotFoundError(f"Segment file was not created: {segment_path}")
                                
                            # Process segment
                            analysis = execute_video_processing(
                                st, segment_path, system_prompt, user_prompt, temperature,
                                frames_per_second, analysis_subdir, segment_num, video_duration
                            )
                            st.markdown(f"**Analysis**: {analysis}", unsafe_allow_html=True)
                            
                        except Exception as ex:
                            print(f"Error processing segment {start_time_seg}-{end_time_seg}: {str(ex)}")
                            st.error(f"Error processing segment {start_time_seg}-{end_time_seg}: {str(ex)}")
                            continue
                        
                        segment_num += 1

                    # Clean up original video file but keep segments
                    os.remove(video_path)
                    print(f"Removed original video file: {video_path}")

                    # After all segments are processed, enable chat
                    analyses = load_all_analyses(analysis_subdir)
                    st.session_state.analyses = analyses
                    st.session_state.show_chat = True

                except Exception as ex:
                    st.error(f"Error processing video file: {str(ex)}")

# STEP 3: CHAT INTERFACE
with chat_container:
    st.header("Step 3: Chat About the Analysis")
    
    if st.session_state.show_chat and st.session_state.analyses is not None:
        # Create a container for the chat with fixed positioning
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        
        # Messages area (scrollable)
        st.markdown('<div class="messages-container">', unsafe_allow_html=True)
        
        # Remove redundant analysis summary - the analysis is already shown in step 2
        
        # Display chat history
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.write(message["content"])
                
        st.markdown('</div>', unsafe_allow_html=True)  # Close messages container
        
        # Chat input area (fixed at bottom)
        st.markdown('<div class="chat-input-container">', unsafe_allow_html=True)
        
        # Chat input with prompt engineering
        placeholder_text = "Ask a question about the video analysis..."
        prompt = st.chat_input(placeholder_text)
        
        if prompt:
            with st.chat_message("user"):
                st.write(prompt)

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                
                for chunk in chat_with_video_analysis(
                    prompt, 
                    st.session_state.analyses,
                    st.session_state.chat_history[:-1],
                    temperature
                ):
                    if chunk.choices[0].delta.content is not None:
                        full_response += chunk.choices[0].delta.content
                        message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
                
            st.session_state.chat_history.extend([
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": full_response}
            ])
            
            # Make sure to keep analyses visible after chat
            st.session_state.displayed_analyses = True
        
        st.markdown('</div>', unsafe_allow_html=True)  # Close input container
        st.markdown('</div>', unsafe_allow_html=True)  # Close chat container
    else:
        st.info("Complete the video analysis to enable chat.")

