import time
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, Response
from app.services.streaming import get_streamer

router = APIRouter()

@router.get("/stream")
def get_video_stream(store_id: str = "STORE-DLF-01", heatmap: bool = False):
    """
    Returns an MJPEG stream generated from the background RetailVisionPipeline execution.
    Provides smooth, low-overhead native video rendering for browsers.
    """
    streamer = get_streamer(store_id)
    
    def frame_generator():
        # Keep track of last frame to avoid duplicate encodes
        last_frame = None
        while True:
            frame_bytes = streamer.latest_heatmap_frame if heatmap else streamer.latest_standard_frame
            if frame_bytes and frame_bytes != last_frame:
                last_frame = frame_bytes
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            # 30ms sleep matches standard video source rates
            time.sleep(0.03)
            
    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

@router.get("/stream/frame")
def get_single_frame(store_id: str = "STORE-DLF-01", heatmap: bool = False):
    """
    Returns the latest single JPEG frame as a direct image response.
    Used by the Streamlit dashboard (Python-side fetch via httpx → st.image())
    to bypass browser iframe/mixed-content sandbox restrictions on MJPEG streams.
    """
    streamer = get_streamer(store_id)
    frame_bytes = streamer.latest_heatmap_frame if heatmap else streamer.latest_standard_frame
    if frame_bytes:
        return Response(content=frame_bytes, media_type="image/jpeg")
    return Response(status_code=204)  # No content yet — pipeline still initializing

@router.post("/stream/control")
def control_stream(store_id: str = "STORE-DLF-01", play: bool = True):
    """
    Pauses or resumes pipeline processing for a given store.
    """
    streamer = get_streamer(store_id)
    streamer.play = play
    return {"status": "ok", "play": play}

@router.get("/stream/telemetry")
def get_stream_telemetry(store_id: str = "STORE-DLF-01"):
    """
    Fetches raw frame-level live telemetry parameters from the running background processor.
    """
    streamer = get_streamer(store_id)
    return streamer.get_live_telemetry()
