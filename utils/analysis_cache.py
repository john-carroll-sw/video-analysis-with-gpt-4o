import os
import time
import json
import hashlib
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Path to the file that stores video analysis metadata
CACHE_FILE = os.path.join("video", "analysis_cache.json")

def ensure_cache_file():
    """Ensure the cache file exists."""
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    if not os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'w') as f:
            json.dump({}, f)

def get_file_identifier(file) -> Tuple[str, int]:
    """Generate a unique identifier for a file based on name and size."""
    return (file.name, file.size)

def compute_file_hash(file) -> str:
    """Compute a hash of the file contents for more accurate identification."""
    file_content = file.getvalue()  # Get the file content as bytes
    return hashlib.md5(file_content).hexdigest()

def get_analysis_cache() -> Dict:
    """Get the analysis cache from disk."""
    ensure_cache_file()
    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading analysis cache: {str(e)}")
        return {}

def save_analysis_cache(cache: Dict):
    """Save the analysis cache to disk."""
    ensure_cache_file()
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving analysis cache: {str(e)}")

def check_video_analyzed(file) -> Optional[str]:
    """
    Check if a video has been analyzed before.
    
    Args:
        file: The uploaded file object
        
    Returns:
        The path to the analysis directory if found, None otherwise
    """
    if file is None:
        return None
        
    # Look up by file hash
    file_hash = compute_file_hash(file)
    cache = get_analysis_cache()
    
    # Reset file position after reading for hash
    file.seek(0)
    
    if file_hash in cache:
        analysis_path = cache[file_hash]["analysis_dir"]
        # Verify the analysis directory still exists
        if os.path.exists(analysis_path):
            return analysis_path
    
    return None

def register_video_analysis(file, analysis_dir: str):
    """
    Register that a video has been analyzed.
    
    Args:
        file: The uploaded file object
        analysis_dir: The path to the analysis directory
    """
    if file is None:
        return
        
    file_hash = compute_file_hash(file)
    # Reset file position after reading for hash
    file.seek(0)
    
    cache = get_analysis_cache()
    
    # Store metadata about the video and its analysis
    cache[file_hash] = {
        "filename": file.name,
        "size": file.size,
        "analysis_dir": analysis_dir,
        "timestamp": time.time()  # Add timestamp of when analysis was done
    }
    
    save_analysis_cache(cache)

def check_url_analyzed(url, start_time=0, end_time=0) -> Optional[str]:
    """
    Check if a video URL has been analyzed before.
    
    Args:
        url: The video URL
        start_time: Start time for partial video analysis
        end_time: End time for partial video analysis
        
    Returns:
        The path to the analysis directory if found, None otherwise
    """
    if not url:
        return None
        
    # Create a unique identifier for this URL and time range
    url_id = hashlib.md5(f"{url}_{start_time}_{end_time}".encode()).hexdigest()
    
    cache = get_analysis_cache()
    
    if url_id in cache:
        analysis_path = cache[url_id]["analysis_dir"]
        # Verify the analysis directory still exists
        if os.path.exists(analysis_path):
            return analysis_path
    
    return None

def register_url_analysis(url, analysis_dir, start_time=0, end_time=0):
    """
    Register that a video URL has been analyzed.
    
    Args:
        url: The video URL
        analysis_dir: The path to the analysis directory
        start_time: Start time for partial video analysis
        end_time: End time for partial video analysis
    """
    if not url:
        return
        
    # Create a unique identifier for this URL and time range
    url_id = hashlib.md5(f"{url}_{start_time}_{end_time}".encode()).hexdigest()
    
    cache = get_analysis_cache()
    
    # Store metadata about the video URL and its analysis
    cache[url_id] = {
        "url": url,
        "start_time": start_time,
        "end_time": end_time,
        "analysis_dir": analysis_dir,
        "timestamp": time.time()
    }
    
    save_analysis_cache(cache)

def load_previous_analysis(analysis_dir: str) -> Dict:
    """
    Load the previous analysis results.
    
    Args:
        analysis_dir: The path to the analysis directory
        
    Returns:
        A dictionary with the analysis results
    """
    analyses = []
    try:
        # This would load the analysis files similar to load_all_analyses in video_processing.py
        analysis_subdir = os.path.join(analysis_dir, "analysis")
        files = sorted([f for f in os.listdir(analysis_subdir) if f.endswith('_analysis.json')])
        
        for file in files:
            with open(os.path.join(analysis_subdir, file), 'r') as f:
                analysis_data = json.load(f)
                analyses.append(analysis_data)
                
        return analyses
    except Exception as ex:
        logger.error(f"Error loading previous analysis: {ex}")
        return []
