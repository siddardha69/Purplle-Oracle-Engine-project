import os
import csv
from datetime import datetime
from loguru import logger
from app.services.base import BaseService
from app.models.pos_transaction import POSTransaction
from app.models.store import Store

class POSIngestionService(BaseService):
    """
    Ingests and normalizes transaction registries from retail CSV data sources (pos_transactions.csv).
    """

    def ingest_pos_csv(self, file_path: str = "./data/pos_transactions.csv") -> int:
        """
        Loads local pos_transactions.csv file, normalizes fields, and inserts into DB.
        Returns:
            Count of successfully ingested transaction records.
        """
        if not os.path.exists(file_path):
            logger.error(f"POS Transaction CSV file not found at {file_path}")
            return 0
            
        logger.info(f"Starting POS transactions ingestion from {file_path}...")
        
        success_count = 0
        try:
            with open(file_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                
                # Check for required headers
                headers = reader.fieldnames or []
                required_fields = ["transaction_id", "store_id", "timestamp", "amount_inr"]
                for field in required_fields:
                    if field not in headers:
                        raise ValueError(f"Missing required CSV column: {field}")
                
                for row in reader:
                    txn_id = row["transaction_id"].strip()
                    store_id = row["store_id"].strip()
                    raw_ts = row["timestamp"].strip()
                    raw_amount = row["amount_inr"].strip()
                    
                    # 1. Normalize UTC Timestamps
                    # Example: 2026-06-01T10:15:30Z
                    try:
                        clean_ts = raw_ts.replace("Z", "")
                        if "T" in clean_ts:
                            parsed_dt = datetime.fromisoformat(clean_ts)
                        else:
                            parsed_dt = datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S")
                    except Exception as ts_err:
                        logger.error(f"Invalid timestamp format '{raw_ts}' in row {txn_id}: {ts_err}")
                        continue
                        
                    # 2. Normalize Amount
                    try:
                        amount = float(raw_amount)
                    except ValueError:
                        logger.error(f"Invalid amount '{raw_amount}' in row {txn_id}")
                        continue
                        
                    # Verify target Store exists in DB, if not, skip or alert
                    store_exists = self.db.query(Store).filter(Store.id == store_id).first()
                    if not store_exists:
                        logger.warning(f"Store ID {store_id} does not exist. Skipping transaction {txn_id}.")
                        continue
                        
                    # 3. Prevent duplicate imports
                    existing = self.db.query(POSTransaction).filter(POSTransaction.transaction_id == txn_id).first()
                    if existing:
                        # Update fields or skip
                        existing.timestamp = parsed_dt
                        existing.amount = amount
                        existing.billing_counter = f"COUNTER-{int(hash(txn_id) % 3) + 1}"
                        success_count += 1
                        continue
                        
                    # 4. Instantiate and store POS Transaction
                    billing_counter = f"COUNTER-{int(hash(txn_id) % 3) + 1}"
                    new_txn = POSTransaction(
                        transaction_id=txn_id,
                        timestamp=parsed_dt,
                        amount=amount,
                        store_id=store_id,
                        billing_counter=billing_counter
                    )
                    
                    self.db.add(new_txn)
                    success_count += 1
                    
            self.db.commit()
            logger.info(f"Ingestion finalized. Successfully synced {success_count} POS records.")
            
        except Exception as e:
            logger.error(f"Failed to ingest POS transaction logs: {e}")
            self.db.rollback()
            
        return success_count
