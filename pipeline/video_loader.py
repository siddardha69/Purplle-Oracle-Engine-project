import os
import time
from typing import Generator, Tuple, Dict, Any, Optional
import cv2
from loguru import logger
from pipeline.config import pipeline_settings

class VideoLoader:
    """
    Manages robust ingestion, frame decoding, and metadata extraction of retail CCTV video files.
    """
    def __init__(self, video_path: str = None):
        self.video_path = video_path or pipeline_settings.VIDEO_PATH
        self.cap = None
        self.fps = 0.0
        self.width = 0
        self.height = 0
        self.total_frames = 0
        self.duration_seconds = 0.0
        self.current_frame_idx = 0
        
        # Enforce file validations
        if not os.path.exists(self.video_path):
            logger.warning(f"Target CCTV video file not found at path: {self.video_path}")
            import glob
            # Use absolute path anchored to this file's location so it works from any CWD
            _videos_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "videos")
            fallback_videos = sorted(glob.glob(os.path.join(_videos_dir, "*.mp4")))
            if fallback_videos:
                self.video_path = fallback_videos[0]
                logger.info(f"Dynamically falling back to available CCTV stream: {self.video_path}")
            else:
                raise FileNotFoundError(f"Video file does not exist: {self.video_path}")
            
        self._initialize_video()

    def _initialize_video(self):
        """
        Loads OpenCV capture context and populates metadata structures.
        """
        try:
            logger.info(f"Opening CCTV video source: {self.video_path}")
            self.cap = cv2.VideoCapture(self.video_path)
            
            if not self.cap.isOpened():
                raise ValueError(f"OpenCV failed to open capture source: {self.video_path}")
                
            # Extract video metadata
            self.fps = float(self.cap.get(cv2.CAP_PROP_FPS))
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Safe protection against division by zero on corrupted fps streams
            if self.fps <= 0.0:
                self.fps = 25.0
                
            self.duration_seconds = self.total_frames / self.fps
            self.current_frame_idx = 0
            
            logger.info(
                f"Video initialization successful. "
                f"Resolution: {self.width}x{self.height} | "
                f"Frame rate: {self.fps:.2f} FPS | "
                f"Total Frames: {self.total_frames} | "
                f"Duration: {self.duration_seconds:.2f}s"
            )
        except Exception as e:
            logger.error(f"Fatal error initializing VideoLoader: {e}")
            self.release()
            raise e

    def get_metadata(self) -> Dict[str, Any]:
        """
        Returns structured video file profile parameters.
        """
        return {
            "video_path": self.video_path,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "total_frames": self.total_frames,
            "duration_seconds": self.duration_seconds
        }

    def generate_frame_timestamp(self, frame_index: int) -> str:
        """
        Generates clean ISO 8601 timestamps corresponding to the relative video playback timeline.
        Starts from current system time (or constant epoch) and increments by frame indexes.
        """
        # Baseline starting epoch: June 1, 2026 10:00:00 AM local time
        base_epoch = 1780299600.0 
        seconds_offset = frame_index / self.fps
        timestamp_epoch = base_epoch + seconds_offset
        
        # Output standard ISO 8601 formatting: YYYY-MM-DDTHH:MM:SS.SSSZ
        utc_time = time.gmtime(timestamp_epoch)
        ms = int((timestamp_epoch % 1) * 1000)
        
        iso_str = (
            f"{time.strftime('%Y-%m-%dT%H:%M:%S', utc_time)}."
            f"{ms:03d}Z"
        )
        return iso_str

    def iter_frames(self, frame_skip: int = None) -> Generator[Tuple[int, str, Any], None, None]:
        """
        Generates frame objects, indices, and timeline indices.
        Supports frame skipping ratios to speed up evaluations.
        """
        skip = frame_skip if frame_skip is not None else pipeline_settings.FRAME_SKIP
        
        if not self.cap or not self.cap.isOpened():
            # Re-initialize the capture if it was released (e.g. after video loop)
            try:
                self._initialize_video()
            except Exception as reinit_err:
                logger.error(f"Cannot re-initialize video capture: {reinit_err}")
                return

        try:
            while True:
                # Handle frames skipping indices
                if skip > 0:
                    target_frame = self.current_frame_idx + skip + 1
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                    self.current_frame_idx = target_frame
                else:
                    self.current_frame_idx += 1

                ret, frame = self.cap.read()
                if not ret:
                    logger.info("End of video stream reached.")
                    break

                # Output coordinates frame details
                timestamp = self.generate_frame_timestamp(self.current_frame_idx)
                yield self.current_frame_idx, timestamp, frame
                
        except Exception as e:
            logger.error(f"Error during video frame decoding loop: {e}")
        finally:
            self.release()

    def release(self):
        """
        Releases capture resource links cleanly.
        """
        if self.cap:
            self.cap.release()
            logger.info("Video capture released cleanly.")
        self.cap = None
