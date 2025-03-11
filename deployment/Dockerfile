FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Add Redis dependency for session management
RUN pip install --no-cache-dir redis

# Create folder for video storage
RUN mkdir -p video

# Set environment variable to run Streamlit in headless mode
ENV STREAMLIT_SERVER_HEADLESS=true

# Expose the port Streamlit runs on
EXPOSE 8501

# Entry command to run the modified Streamlit app
CMD ["python", "-m", "streamlit", "run", "Video_Analysis_With_LLMs.py"]
