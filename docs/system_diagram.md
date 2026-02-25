# System Architecture Diagram

## Full Integration Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         RETAIL STORE                                │
│                                                                     │
│   [RFID Tags on Items]                                              │
│         │ radio signal                                              │
│         ▼                                                           │
│   [Handheld RFID Reader]  ──────────────────────────────────────┐  │
│                                                                  │  │
│   [Square POS Terminal]  ──── payment.completed webhook ──────┐ │  │
│                                                                │ │  │
└────────────────────────────────────────────────────────────────┼─┼──┘
                                                                 │ │
                                                                 ▼ ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        CLOUD LAYER                                  │
│                                                                     │
│  ┌──────────────────────┐         ┌──────────────────────────────┐  │
│  │   Nedap iD Cloud     │         │     Square Backend            │  │
│  │                      │         │                              │  │
│  │  - EPC repository    │         │  - Catalog (SKUs)            │  │
│  │  - Item status       │◄───────►│  - Inventory counts          │  │
│  │  - Location tracking │         │  - Webhook events            │  │
│  │  - EPCIS events      │         │  - Orders & payments         │  │
│  └──────────┬───────────┘         └──────────────┬───────────────┘  │
│             │                                    │                  │
│             │    REST API (JSON)                  │    Webhooks      │
│             └──────────────┬───────────────────── ┘                  │
│                            │                                        │
│                            ▼                                        │
│              ┌─────────────────────────┐                            │
│              │       MIDDLEWARE        │                            │
│              │  rfid_to_square_sync.py │                            │
│              │                        │                            │
│              │  Flow A (Scan → Square) │                            │
│              │  1. Fetch EPCs from     │                            │
│              │     iD Cloud            │                            │
│              │  2. Group by SKU        │                            │
│              │  3. Count per SKU       │                            │
│              │  4. Push to Square      │                            │
│              │     Inventory API       │                            │
│              │                        │                            │
│              │  Flow B (Sale → iCloud) │                            │
│              │  1. Receive Square      │                            │
│              │     webhook             │                            │
│              │  2. Parse line items    │                            │
│              │  3. FIFO: pick EPC      │                            │
│              │  4. Retire EPC in       │                            │
│              │     iD Cloud            │                            │
│              └─────────────────────────┘                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The Translation Problem (Visualized)

### What iD Cloud sends after a scan:
```json
{ "items": [
    { "epc": "...001A01", "sku": "BJM-001-BLU-M", "status": "in_store" },
    { "epc": "...001A02", "sku": "BJM-001-BLU-M", "status": "in_store" },
    { "epc": "...001A03", "sku": "BJM-001-BLU-M", "status": "in_store" },
    { "epc": "...001A04", "sku": "BJM-001-BLU-L", "status": "in_store" },
    ...30 total items
]}
```

### After middleware aggregation:
```
BJM-001-BLU-M  →  3 EPCs  →  count: 3
BJM-001-BLU-L  →  1 EPC   →  count: 1
```

### What Square receives:
```json
{ "changes": [
    { "type": "PHYSICAL_COUNT",
      "physical_count": {
        "catalog_object_id": "LJCY6ZQNNHBP5A",
        "location_id": "LMND7X2QKFP93",
        "quantity": "3"
      }
    }, ...
]}
```

---

## Data Flow Timing

```
FLOW A  (triggered by RFID scan, typically 1–3x per day)
────────────────────────────────────────────────────────
  iD Cloud scan complete
        │
        ▼ (~seconds)
  Middleware aggregates EPCs → SKU counts
        │
        ▼ (~seconds)
  Square inventory updated (PHYSICAL_COUNT)
        │
        ▼
  Website "In Stock" availability refreshed ✓


FLOW B  (triggered in real time per transaction)
────────────────────────────────────────────────────────
  Customer purchases item at Square POS
        │
        ▼ (<1 second)
  Square fires payment.completed webhook
        │
        ▼ (<1 second)
  Middleware parses SKUs sold, selects EPCs (FIFO)
        │
        ▼ (<1 second)
  iD Cloud marks EPC(s) as sold
        │
        ▼
  Item-level audit trail updated ✓
```
