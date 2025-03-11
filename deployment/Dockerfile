# Use the official Python image from the Docker Hub
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install dependencies for OpenCV and other necessary libraries
RUN apt-get update && apt-get install -y \
    libgl1 \
    libgl1-mesa-glx \
    libgl1-mesa-dri \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Set environment variable for Streamlit
ENV STREAMLIT_SERVER_PORT=8000
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLE_CORS=false

# Default entry point is app.py but can be overridden
ARG ENTRY_FILE=app.py
ENV ENTRY_FILE=${ENTRY_FILE}

# Expose port
EXPOSE 8000

# Start the Streamlit app with additional debug information
CMD echo "Starting Streamlit app with Python $(python --version)" && \
    streamlit --version && \
    streamlit run $ENTRY_FILE --server.port 8000 --server.enableCORS false --server.enableXsrfProtection false
