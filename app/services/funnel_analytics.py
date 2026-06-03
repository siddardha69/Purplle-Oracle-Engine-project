from typing import Dict, Any, List
from loguru import logger
from sqlalchemy import func
from app.services.base import BaseService
from app.models.session import VisitorSession
from app.models.event import VisitorEvent

class FunnelAnalyticsService(BaseService):
    """
    Computes retail conversion funnels using real-time database queries.
    Tracks step-by-step shopper drops and checkout purchases ratios.
    """

    def calculate_funnel(self, store_id: str) -> Dict[str, Any]:
        """
        Runs analytical queries to generate real conversion funnels.
        """
        logger.info(f"Computing real conversion funnel metrics for store: {store_id}")
        
        # 1. Total Entrants (Count of active sessions)
        total_entrants = self.db.query(VisitorSession).filter(VisitorSession.store_id == store_id).count()
        
        if total_entrants == 0:
            return {
                "store_id": store_id,
                "total_visitors": 0,
                "product_visitors": 0,
                "checkout_visitors": 0,
                "purchased_visitors": 0,
                "steps": [
                    {"step": "store_entrance", "visitors": 0, "conversion_rate": 0.0, "dropoff_rate": 0.0},
                    {"step": "product_zones", "visitors": 0, "conversion_rate": 0.0, "dropoff_rate": 0.0},
                    {"step": "checkout_counter", "visitors": 0, "conversion_rate": 0.0, "dropoff_rate": 0.0},
                    {"step": "pos_checkout_completed", "visitors": 0, "conversion_rate": 0.0, "dropoff_rate": 0.0}
                ],
                "overall_conversion_rate": 0.0,
                "checkout_conversion_rate": 0.0,
                "dropoff_rate": 0.0
            }

        # 2. Product Discovery Visitors (Traversed merchandise polygons)
        product_visitors = (
            self.db.query(func.count(func.distinct(VisitorSession.id)))
            .join(VisitorEvent, VisitorSession.id == VisitorEvent.session_id)
            .filter(VisitorSession.store_id == store_id)
            .filter(VisitorEvent.zone_name.in_(["makeup_zone", "skincare_zone", "fragrance_counter"]))
            .scalar() or 0
        )
        
        # 3. Checkout Queue Entrants
        checkout_visitors = (
            self.db.query(func.count(func.distinct(VisitorSession.id)))
            .join(VisitorEvent, VisitorSession.id == VisitorEvent.session_id)
            .filter(VisitorSession.store_id == store_id)
            .filter(VisitorEvent.zone_name.in_(["checkout_zone", "checkout_counter", "billing_zone"]))
            .scalar() or 0
        )
        
        # 4. Confirmed POS Purchases (converted == True)
        purchased_visitors = (
            self.db.query(VisitorSession)
            .filter(VisitorSession.store_id == store_id)
            .filter(VisitorSession.converted == True)
            .count()
        )

        # Step 1: Entrance
        step1_rate = 100.0
        step1_drop = 0.0
        
        # Step 2: Product Discovery
        step2_rate = round((product_visitors / total_entrants) * 100.0, 2) if total_entrants > 0 else 0.0
        step2_drop = round(100.0 - step2_rate, 2)
        
        # Step 3: Checkout Queue
        step3_rate = round((checkout_visitors / product_visitors) * 100.0, 2) if product_visitors > 0 else 0.0
        step3_drop = round(100.0 - step3_rate, 2)
        
        # Step 4: POS Purchase
        step4_rate = round((purchased_visitors / checkout_visitors) * 100.0, 2) if checkout_visitors > 0 else 0.0
        step4_drop = round(100.0 - step4_rate, 2)

        steps = [
            {"step": "store_entrance", "visitors": total_entrants, "conversion_rate": step1_rate, "dropoff_rate": step1_drop},
            {"step": "product_zones", "visitors": product_visitors, "conversion_rate": step2_rate, "dropoff_rate": step2_drop},
            {"step": "checkout_counter", "visitors": checkout_visitors, "conversion_rate": step3_rate, "dropoff_rate": step3_drop},
            {"step": "pos_checkout_completed", "visitors": purchased_visitors, "conversion_rate": step4_rate, "dropoff_rate": step4_drop}
        ]

        overall_conversion = round((purchased_visitors / total_entrants) * 100.0, 2) if total_entrants > 0 else 0.0
        checkout_conversion = round((purchased_visitors / checkout_visitors) * 100.0, 2) if checkout_visitors > 0 else 0.0
        dropoff_rate = round(100.0 - overall_conversion, 2)

        return {
            "store_id": store_id,
            "total_visitors": total_entrants,
            "product_visitors": product_visitors,
            "checkout_visitors": checkout_visitors,
            "purchased_visitors": purchased_visitors,
            "steps": steps,
            "overall_conversion_rate": overall_conversion,
            "checkout_conversion_rate": checkout_conversion,
            "dropoff_rate": dropoff_rate
        }
