# Use an older but more stable Python image 
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Install dependencies for OpenCV with optimized space usage
# The key changes are combining commands and clearing apt cache in the same layer
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
    # Minimal dependencies for OpenCV and video processing
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    # Clean up in the same layer to reduce image size
    && rm -rf /var/cache/apt/* /var/lib/apt/lists/* \
    && apt-get clean

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Create necessary directories
RUN mkdir -p video frames

# Set environment variables for servers
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLECORS=false
ENV AUTH_SERVER_PORT=5555
ENV AUTH_SERVER_ADDRESS=0.0.0.0
ENV PYTHONUNBUFFERED=1

# Expose both Streamlit and Auth server ports
EXPOSE 8501 5555

# Set entry point to start_app.py which will handle auth if enabled
CMD ["python", "start_app.py"]
