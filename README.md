# Video Analysis with LLMs

This project provides tools for analyzing video content using Large Language Models (LLMs), particularly GPT-4o with vision capabilities. The application can process videos from local files or URLs, segment them for efficient analysis, extract audio transcriptions, and provide AI-powered insights about the video content.

## Table of Contents

- [Video Analysis with LLMs](#video-analysis-with-llms)
  - [Table of Contents](#table-of-contents)
  - [Main Application: Video Analysis with LLMs](#main-application-video-analysis-with-llms)
    - [Key Features](#key-features)
    - [Getting Started](#getting-started)
      - [Prerequisites](#prerequisites)
      - [Installation](#installation)
      - [Running the Application](#running-the-application)
    - [Usage Guide](#usage-guide)
  - [Original Applications](#original-applications)
    - [Video Analysis with GPT-4o](#video-analysis-with-gpt-4o)
      - [Usage](#usage)
      - [Parameters](#parameters)
      - [Example](#example)
      - [Deployment](#deployment)
    - [Video Shot Analysis](#video-shot-analysis)
      - [Usage](#usage-1)
      - [Parameters](#parameters-1)
      - [Example](#example-1)
      - [Demo](#demo)
      - [Deployment](#deployment-1)
  - [Project Organization](#project-organization)
  - [Additional Information](#additional-information)
    - [Customization](#customization)
    - [Analysis Cache](#analysis-cache)
  - [Environment Configuration](#environment-configuration)
    - [Set up a Python Virtual Environment](#set-up-a-python-virtual-environment)

## Main Application: Video Analysis with LLMs

The primary application (`Video_Analysis_With_LLMs.py`) is a full-featured Streamlit app that provides an intuitive interface for video analysis.

### Key Features

- Process videos from local files or YouTube/URLs
- Split videos into manageable segments
- Extract and analyze frames at configurable rates
- Transcribe audio using Whisper
- Generate detailed analysis using GPT-4o
- Interactive chat with the AI about video content
- Caching of analysis results for repeated queries
- Customizable analysis configuration

### Getting Started

#### Prerequisites

1. Python 3.8+ installed
2. Azure OpenAI API access with GPT-4o deployment
3. Azure Whisper API access (for audio transcription)

#### Installation

1. Clone the repository:
```
git clone https://github.com/your-repo/video-analysis-with-llms.git
cd video-analysis-with-llms
```

2. Set up a Python virtual environment:
```
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

3. Install the required packages:
```
pip install -r requirements.txt
```

4. Configure environment variables:
Create a `.env` file in the root directory of your project with the following content. You can use the provided [`.env-sample`](.env-sample) as a template:

```
SYSTEM_PROMPT="You are an expert on Video Analysis. You will be shown a series of images from a video. Describe what is happening in the video, including the objects, actions, and any other relevant details. Be as specific and detailed as possible."

AZURE_OPENAI_ENDPOINT=<your_azure_openai_endpoint>
AZURE_OPENAI_API_KEY=<your_azure_openai_api_key>
AZURE_OPENAI_API_VERSION=<your_azure_openai_api_version>
AZURE_OPENAI_DEPLOYMENT_NAME=<your_azure_openai_deployment_name>

WHISPER_ENDPOINT=<your_whisper_endpoint>
WHISPER_API_KEY=<your_whisper_api_key>
WHISPER_API_VERSION=<your_whisper_api_version>
WHISPER_DEPLOYMENT_NAME=<your_whisper_deployment_name>
```

#### Running the Application

To run the `Video_Analysis_With_LLMs.py` script, execute the following command:
```
streamlit run Video_Analysis_With_LLMs.py
```

### Usage Guide

The application provides an intuitive interface for video analysis. Follow the on-screen instructions to upload a video or provide a URL, configure the analysis parameters, and start the analysis.

## Original Applications

### Video Analysis with GPT-4o

The `video-analysis-with-gpt-4o.py` script demonstrates the capabilities of GPT-4o to analyze and extract insights from a video file or a video URL (e.g., YouTube). This script is useful for analyzing videos in detail by splitting them into smaller segments and extracting frames at a specified rate. This allows for a more granular analysis of the video content, making it easier to identify specific events, actions, or objects within the video. This script is particularly useful for:

- Detailed video analysis for research or academic purposes.
- Analyzing training or instructional videos to extract key moments.
- Reviewing security footage to identify specific incidents.

Here is the code of this demo: [video-analysis-with-gpt-4o.py](video-analysis-with-gpt-4o.py)

#### Usage

To run the `video-analysis-with-gpt-4o.py` script, execute the following command:
```
streamlit run video-analysis-with-gpt-4o.py
```

#### Parameters

- **Video source**: Select whether the video is from a file or a URL.
- **Continuous transmission**: Check this if the video is a continuous transmission.
- **Transcribe audio**: Check this to transcribe the audio using Whisper.
- **Show audio transcription**: Check this to display the audio transcription.
- **Number of seconds to split the video**: Specify the interval for each video segment.
- **Number of seconds per frame**: Specify the number of seconds between each frame extraction.
- **Frames resizing ratio**: Specify the resizing ratio for the frames.
- **Save the frames**: Check this to save the extracted frames to the "frames" folder.
- **Temperature for the model**: Specify the temperature for the GPT-4o model.
- **System Prompt**: Enter the system prompt for the GPT-4o model.
- **User Prompt**: Enter the user prompt for the GPT-4o model.

#### Example

To analyze a YouTube video with a segment interval of 60 seconds, extracting 1 frame every 30 seconds, you would set the parameters as follows:

- **Video source**: URL
- **URL**: `https://www.youtube.com/watch?v=example`
- **Number of seconds to split the video**: 60
- **Number of seconds per frame**: 30

Then click the "Analyze video" button to start the analysis.

A screenshot:

<img src="./Screenshot.png" alt="Sample Screenshot"/>

#### Deployment

To deploy the `video-analysis-with-gpt-4o.py` script on your Azure tenant in an Azure Container Registry (Docker), follow these steps:

1. Ensure you have the necessary environment variables set in your `.env` file.
2. Use the provided [deploy.sh](deploy.sh) or [deploy.ps1](deploy.ps1) script to build and deploy the Docker image.

For Bash:
```sh
./deploy.sh VideoAnalysisGpt4o video-analysis-with-gpt-4o.py
```

For PowerShell:
```powershell
pwsh ./deploy.ps1 -Prefix VideoAnalysisGpt4o -PythonScript video-analysis-with-gpt-4o.py
```

This will build the Docker image using the [Dockerfile](Dockerfile) and deploy it to Azure App Service.

### Video Shot Analysis

The `video_shot_analysis.py` script will download the specified video, split it into shots based on the defined interval, extract frames at the specified rate, perform the analysis on each shot, and save the analysis results to JSON files in the analysis subdirectory within the main video analysis directory. If `max_duration` is set, only up to that duration of the video will be processed. This script is useful for:

- Detailed video analysis for research or academic purposes.
- Analyzing training or instructional videos to extract key moments.
- Reviewing security footage to identify specific incidents.

Here is the code of this demo: [video_shot_analysis.py](video_shot_analysis.py)

#### Usage

To run the `video_shot_analysis.py` script, execute the following command:
```
streamlit run video_shot_analysis.py
```

#### Parameters

- **Video source**: Select whether the video is from a file or a URL.
- **Continuous transmission**: Check this if the video is a continuous transmission.
- **Transcribe audio**: Check this to transcribe the audio using Whisper.
- **Show audio transcription**: Check this to display the audio transcription.
- **Shot interval in seconds**: Specify the interval for each video shot.
- **Frames per second**: Specify the number of frames to extract per second.
- **Frames resizing ratio**: Specify the resizing ratio for the frames.
- **Save the frames**: Check this to save the extracted frames to the "frames" folder.
- **Temperature for the model**: Specify the temperature for the GPT-4o model.
- **System Prompt**: Enter the system prompt for the GPT-4o model.
- **User Prompt**: Enter the user prompt for the GPT-4o model.
- **Maximum duration to process (seconds)**: Specify the maximum duration of the video to process. If the video is longer, only this duration will be processed. Set to 0 to process the entire video.

#### Example

To analyze a YouTube video with a shot interval of 60 seconds, extracting 1 frame per second, and processing only the first 120 seconds of the video, you would set the parameters as follows:

- **Video source**: URL
- **URL**: `https://www.youtube.com/watch?v=example`
- **Shot interval in seconds**: 60
- **Frames per second**: 1
- **Maximum duration to process (seconds)**: 120

Then click the "Analyze video" button to start the analysis.

#### Demo
![Video Shot Analysis Demo](https://raw.githubusercontent.com/john-carroll-sw/video-analysis-with-gpt-4o/main/VideoShotAnalysisDemo.gif)

#### Deployment

To deploy the `video_shot_analysis.py` script on your Azure tenant in an Azure Container Registry (Docker), follow these steps:

1. Ensure you have the necessary environment variables set in your `.env` file.
2. Use the provided [deploy.sh](deploy.sh) or [deploy.ps1](deploy.ps1) script to build and deploy the Docker image.

For Bash:
```sh
./deploy.sh VideoShotAnalysis video_shot_analysis.py
```

For PowerShell:
```powershell
pwsh ./deploy.ps1 -Prefix VideoShotAnalysis -PythonScript video_shot_analysis.py
```

This will build the Docker image using the [Dockerfile](Dockerfile) and deploy it to Azure App Service.

## Project Organization

The project is organized as follows:

- `Video_Analysis_With_LLMs.py`: Main application script
- `video-analysis-with-gpt-4o.py`: Original video analysis script
- `video_shot_analysis.py`: Original video shot analysis script
- `yt_video_downloader.py`: YouTube video downloader script
- `requirements.txt`: List of required Python packages
- `deploy.sh`: Deployment script for Bash
- `deploy.ps1`: Deployment script for PowerShell
- `.env-sample`: Sample environment configuration file

## Additional Information

### Customization

The application can be customized by modifying the configuration parameters in the `.env` file and the Streamlit interface elements in the `Video_Analysis_With_LLMs.py` script.

### Analysis Cache

The application caches analysis results to speed up repeated queries. The cache is stored in the `cache` directory and can be cleared by deleting the contents of this directory.

## Environment Configuration

### Set up a Python Virtual Environment

1. Open the Command Palette (Ctrl+Shift+P).
1. Search for **Python: Create Environment**.
1. Select **Venv**.
1. Select a Python interpreter. Choose 3.10 or later.

It can take a minute to set up. If you run into problems, see [Python environments in VS Code](https://code.visualstudio.com/docs/python/environments).
