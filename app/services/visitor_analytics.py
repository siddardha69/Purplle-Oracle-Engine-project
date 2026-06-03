from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from loguru import logger
from app.services.base import BaseService
from app.models.session import VisitorSession
from app.models.event import VisitorEvent

class VisitorAnalyticsService(BaseService):
    """
    Computes precise movement telemetry metrics for individual shopper trajectories.
    Translates coordinate transitions into granular session logs.
    """

    def analyze_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Analyzes movement traces and transition intervals for an individual session.
        """
        session = self.db.query(VisitorSession).filter(VisitorSession.id == session_id).first()
        if not session:
            logger.warning(f"Visitor Session {session_id} not found in database.")
            return None
            
        # Pull and sort movements chronologically
        events = (
            self.db.query(VisitorEvent)
            .filter(VisitorEvent.session_id == session_id)
            .order_by(VisitorEvent.event_timestamp.asc())
            .all()
        )
        
        if not events:
            return {
                "session_id": session_id,
                "visitor_track_id": session.visitor_track_id,
                "entry_time": session.start_time,
                "exit_time": session.end_time,
                "visit_duration": session.dwell_time,
                "zones_visited": [],
                "dwell_per_zone": {},
                "session_length": session.dwell_time,
                "checkout_reached": False,
                "converted": session.converted
            }

        # 1. Timestamps & Durations
        entry_time = events[0].event_timestamp
        
        # Check if they have officially exited
        has_exited = any(e.event_type == "EXIT" and e.zone_name == "store_entrance" for e in events) or session.end_time is not None
        exit_time = session.end_time or events[-1].event_timestamp
        
        visit_duration = (exit_time - entry_time).total_seconds()
        
        # 2. Zones Visited & Dwells
        zones_visited: Set[str] = set()
        dwell_per_zone: Dict[str, float] = {}
        
        for event in events:
            zone = event.zone_name
            if event.event_type in ["ENTER", "ZONE_ENTER"]:
                zones_visited.add(zone)
            elif event.event_type in ["EXIT", "ZONE_EXIT"]:
                # The pipeline records total dwell duration in seconds in event.duration
                duration = event.duration or 0.0
                dwell_per_zone[zone] = dwell_per_zone.get(zone, 0.0) + duration

        # Fallback zone calculation: if duration was 0 or missing, estimate from time delta
        for zone in zones_visited:
            if zone not in dwell_per_zone or dwell_per_zone[zone] == 0:
                # Find enter and exit events for this zone and calculate delta
                enters = [e.event_timestamp for e in events if e.zone_name == zone and e.event_type in ["ENTER", "ZONE_ENTER"]]
                exits = [e.event_timestamp for e in events if e.zone_name == zone and e.event_type in ["EXIT", "ZONE_EXIT"]]
                if enters and exits:
                    delta = (max(exits) - min(enters)).total_seconds()
                    if delta > 0:
                        dwell_per_zone[zone] = delta

        # 3. Checkout Reached validation
        checkout_zones = ["checkout_zone", "checkout_counter", "billing_zone"]
        checkout_reached = any(z in zones_visited for z in checkout_zones)
        
        return {
            "session_id": session_id,
            "visitor_track_id": session.visitor_track_id,
            "entry_time": entry_time,
            "exit_time": exit_time if has_exited else None,
            "visit_duration": round(visit_duration, 1),
            "zones_visited": list(zones_visited),
            "dwell_per_zone": {k: round(v, 1) for k, v in dwell_per_zone.items()},
            "session_length": round(visit_duration, 1),
            "checkout_reached": checkout_reached,
            "converted": session.converted
        }

    def analyze_all_active_sessions(self, store_id: str) -> List[Dict[str, Any]]:
        """
        Performs batch sequence analytics across active store visitors.
        """
        sessions = self.db.query(VisitorSession).filter(VisitorSession.store_id == store_id).all()
        analyzed = []
        for s in sessions:
            res = self.analyze_session(s.id)
            if res:
                analyzed.append(res)
        return analyzed
