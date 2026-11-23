# ER / Data Model

Server database: PostgreSQL 16 (Docker locally, Azure Database for PostgreSQL Flexible Server in the cloud).
Schema is managed by Alembic (`services/billing_api/alembic/versions/0001_initial_schema.py`).

```mermaid
erDiagram
    SUBSCRIBER ||--o{ USAGE_RECORD : "records"
    SUBSCRIBER ||--o{ BILL : "is billed"
    BILL ||--o{ PAYMENT : "is paid by"

    SUBSCRIBER {
        int id PK
        varchar subscriber_no UK "login identity, JWT sub"
        varchar full_name
        varchar password_hash "bcrypt"
        varchar role "SUBSCRIBER | ADMIN"
        timestamptz created_at
    }
    USAGE_RECORD {
        int id PK
        int subscriber_id FK
        int year
        int month "1-12"
        varchar usage_type "PHONE | INTERNET"
        int events "Add Usage events in this call"
        int quantity "minutes (10/event) or MB (1/event)"
        timestamptz created_at
    }
    BILL {
        int id PK
        int subscriber_id FK
        int year
        int month "UK(subscriber_id, year, month)"
        int phone_minutes
        int internet_mb
        numeric phone_charge "10,2"
        numeric internet_charge "10,2"
        numeric total "10,2"
        numeric paid_amount "10,2, >= 0"
        varchar status "UNPAID | PARTIAL | PAID"
        timestamptz calculated_at
    }
    PAYMENT {
        int id PK
        int bill_id FK
        varchar transaction_id UK "idempotency key"
        numeric amount "10,2, > 0"
        varchar status
        timestamptz created_at
    }
```

## Design notes
- **Money** is `NUMERIC(10,2)`, never floating point.
- **Usage** is stored as integer minutes / MB. Each Add Usage event records a fixed 10 minutes (phone) or 1 MB (internet), per Billing Guide §2.3 and §3.3.
- **One bill per subscriber per month** (unique constraint). Recalculating a bill updates usage and charges but keeps `paid_amount`.
- **Duplicate payments** are prevented by the unique `transaction_id` (Billing Guide §5.3).
- **Remaining balance** (`total − paid_amount`) and **due date** (month end + 15 days, §6.1) are derived, not stored.
