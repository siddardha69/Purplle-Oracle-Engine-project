# 💳 POS Transaction Specifications

Place POS checkout ledger entries inside this directory.

## Expected Specifications:
- **Format**: `pos_transactions.csv`
- **Required Columns**:
  - `transaction_id`: Unique registry identifier.
  - `store_id`: Mapped storefront identifier.
  - `timestamp`: ISO-8601 formatted UTC date-time string (`YYYY-MM-DDTHH:MM:SSZ`).
  - `amount_inr`: Numerical total spent by client.
  - `visitor_track_id`: (Optional) Ground-truth track ID link if seeded.
  - `items_count`: Numerical count of purchased items.
