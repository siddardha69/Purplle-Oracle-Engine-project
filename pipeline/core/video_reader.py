import time
import cv2
from loguru import logger

class VideoStreamReader:
    """
    Manages robust OpenCV stream ingestion from camera feeds.
    Includes active auto-reconnection frames to prevent pipe breakdowns in production.
    """
    def __init__(self, source: str):
        self.source = source
        self.cap = None
        self.is_running = False
        self._open_stream()

    def _open_stream(self):
        """
        Attempts to open target RTSP or video file streams.
        """
        logger.info(f"Opening camera input stream: {self.source}")
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            logger.error(f"Failed to open video source: {self.source}")
        else:
            logger.info("Camera input stream established successfully.")
            self.is_running = True

    def read_frame(self):
        """
        Decodes a frame. Automatically triggers reconnects if empty frames are returned.
        """
        if not self.cap or not self.cap.isOpened():
            self._reconnect()
            return None, False

        ret, frame = self.cap.read()
        if not ret:
            logger.warning("Empty frame parsed. Stream connection may have dropped.")
            self._reconnect()
            return None, False

        return frame, True

    def _reconnect(self):
        """
        Runs connection retries, sleeping incrementally to prevent resource flooding.
        """
        logger.warning(f"Attempting to rebuild connection for source: {self.source}")
        self.is_running = False
        if self.cap:
            self.cap.release()
            
        retry_delay = 2.0
        max_delay = 30.0
        
        while not self.is_running:
            try:
                self._open_stream()
                if self.cap.isOpened():
                    self.is_running = True
                    break
            except Exception as e:
                logger.error(f"Reconnection retry failed: {e}")
                
            logger.info(f"Sleeping {retry_delay}s before retrying connection...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)

    def release(self):
        """
        Releases capture pipelines cleanly.
        """
        if self.cap:
            self.cap.release()
            logger.info("Camera capture connection released cleanly.")
        self.is_running = False
