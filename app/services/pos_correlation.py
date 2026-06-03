from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from loguru import logger
from app.services.base import BaseService
from app.models.session import VisitorSession
from app.models.event import VisitorEvent
from app.models.pos_transaction import POSTransaction

class POSCorrelationService(BaseService):
    """
    Data engineering engine correlating movement sessions with POS transactional cash logs.
    Computes spatial-temporal proximity matrices to confirm conversions dynamically.
    """

    def correlate_sessions_to_transactions(self, store_id: str) -> int:
        """
        Scans un-correlated visitor sessions, calculates purchase probabilities,
        and marks converted shoppers in the database.
        Returns:
            Count of successfully correlated sessions.
        """
        logger.info(f"Running POS Transaction Correlation sweeps for store: {store_id}...")
        
        # 1. Fetch all store sessions
        sessions = self.db.query(VisitorSession).filter(VisitorSession.store_id == store_id).all()
        
        # 2. Fetch all POS transactions for this store
        transactions = self.db.query(POSTransaction).filter(POSTransaction.store_id == store_id).all()
        
        if not sessions or not transactions:
            logger.warning("Missing sessions or transactions inside DB to perform correlation analysis.")
            return 0
            
        correlation_count = 0
        
        for session in sessions:
            # If already converted, we can optionally skip or re-evaluate
            # Let's run correlation logic
            best_match: Optional[POSTransaction] = None
            best_probability = 0.0
            
            # Find the session's checkout zone exits
            checkout_events = (
                self.db.query(VisitorEvent)
                .filter(VisitorEvent.session_id == session.id)
                .filter(VisitorEvent.zone_name.in_(["checkout_zone", "checkout_counter", "billing_zone"]))
                .filter(VisitorEvent.event_type == "EXIT")
                .all()
            )
            
            checkout_exit_time = None
            checkout_dwell_s = 0.0
            
            if checkout_events:
                # Use the latest checkout exit event
                checkout_exit_time = max(e.event_timestamp for e in checkout_events)
                checkout_dwell_s = sum(e.duration or 0.0 for e in checkout_events)
            else:
                # Fallback to session end_time if no zone exit was logged
                checkout_exit_time = session.end_time
                
            if not checkout_exit_time:
                # Still inside the store, cannot correlate checkout transactions yet
                continue
                
            # Iterate and score transactions
            for txn in transactions:
                # Proximity window threshold (e.g. 5 minutes / 300s)
                time_diff = abs((checkout_exit_time - txn.timestamp).total_seconds())
                
                if time_diff > 300.0:
                    continue
                    
                # Compute temporal score: decays as time difference increases
                temp_score = 1.0 - (time_diff / 300.0)
                
                # Compute dwell score: shoppers buying items spend at least 45 seconds at checkout
                dwell_score = min(checkout_dwell_s / 45.0, 1.0) if checkout_dwell_s > 0 else 0.5
                
                # Combine scores (70% weight on time proximity, 30% on queue dwell duration)
                prob = (temp_score * 0.70) + (dwell_score * 0.30)
                
                if prob > best_probability:
                    best_probability = prob
                    best_match = txn
            
            # Confirm correlation if probability passes the threshold
            if best_match and best_probability >= 0.65:
                session.converted = True
                correlation_count += 1
                logger.info(
                    f"Correlated visitor session {session.visitor_track_id} to transaction {best_match.transaction_id}. "
                    f"Confidence: {best_probability*100:.1f}% | Time delta: {abs((checkout_exit_time - best_match.timestamp).total_seconds()):.1f}s"
                )
                
        if correlation_count > 0:
            try:
                self.db.commit()
                logger.info(f"POS Correlation committed. Unified {correlation_count} conversion traces.")
            except Exception as e:
                logger.error(f"Failed to commit POS Correlation traces: {e}")
                self.db.rollback()
                
        return correlation_count

    def get_correlation_details(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieves deep correlation probability statistics for a visitor session.
        """
        session = self.db.query(VisitorSession).filter(VisitorSession.id == session_id).first()
        if not session:
            return {"error": "Session not found"}
            
        # Get checkout events details
        checkout_events = (
            self.db.query(VisitorEvent)
            .filter(VisitorEvent.session_id == session_id)
            .filter(VisitorEvent.zone_name.in_(["checkout_zone", "checkout_counter", "billing_zone"]))
            .all()
        )
        
        dwell_s = sum(e.duration or 0.0 for e in checkout_events if e.event_type == "EXIT")
        
        # Pull matching transaction if already converted
        match_id = None
        probability = 0.0
        amount = 0.0
        
        if session.converted:
            # Re-run match to retrieve transaction details
            checkout_exit = session.end_time or (max(e.event_timestamp for e in checkout_events) if checkout_events else None)
            if checkout_exit:
                best_txn = (
                    self.db.query(POSTransaction)
                    .filter(POSTransaction.store_id == session.store_id)
                    .order_by(func.abs(func.julianday(POSTransaction.timestamp) - func.julianday(checkout_exit)).asc())
                    .first()
                )
                if best_txn:
                    match_id = best_txn.transaction_id
                    amount = best_txn.amount
                    time_diff = abs((checkout_exit - best_txn.timestamp).total_seconds())
                    probability = round(max(1.0 - (time_diff / 300.0), 0.70), 2)
                    
        return {
            "session_id": session_id,
            "visitor_track_id": session.visitor_track_id,
            "checkout_dwell_seconds": round(dwell_s, 1),
            "purchase_probability": probability if session.converted else 0.0,
            "purchase_confirmed": session.converted,
            "estimated_transaction_match": match_id,
            "transaction_amount": amount
        }
