# RFID ↔ Square Inventory Sync — Middleware Simulation

A working prototype of the middleware translation layer between **Nedap iD Cloud** (RFID item-level tracking) and **Square POS** (SKU-level inventory management) — built to demonstrate systems thinking around retail inventory architecture.

---

## The Problem This Solves

Enterprise RFID platforms like Nedap iD Cloud track inventory at the **individual item level** — every physical garment has a unique identifier (EPC) that is tracked from factory to sale. Square POS tracks inventory at the **SKU level** — it just needs to know how many units of a product are available.

These two systems speak fundamentally different languages:

| | Nedap iD Cloud | Square POS |
|---|---|---|
| **Unit of tracking** | Individual EPC per item | Count per SKU |
| **Example** | `EPC: 3034257BF400B49000001A01` | `BJM-001-BLU-M: 3 units` |
| **After a sale** | Marks that specific EPC as "sold" | Decrements SKU count by 1 |

This middleware sits between them — translating, aggregating, and keeping both systems in sync in real time.

---

## How It Works

### Flow A: RFID Scan → Square Inventory Update

```
[Nedap iD Cloud]          [Middleware]                [Square POS]
  RFID scan          →    Group EPCs by SKU      →    POST /v2/inventory/changes
  returns 30 EPCs         count per SKU               updates 14 SKU quantities
                          build Square payload
```

After a store associate scans inventory with an RFID reader, iD Cloud returns a list of all detected EPCs. The middleware:
1. Filters for `in_store` items only
2. Groups EPCs by their SKU attribute
3. Counts units per SKU
4. Builds and sends a `PHYSICAL_COUNT` payload to Square's Inventory API

### Flow B: Square Sale → iD Cloud EPC Retirement

```
[Square POS]              [Middleware]                [Nedap iD Cloud]
  payment.completed  →    Parse line items        →    PATCH /epcs/status
  webhook fires           identify SKUs sold           mark specific EPCs as sold
                          FIFO: select EPCs
```

When a sale is completed, Square fires a webhook. The middleware:
1. Parses the sale's line items to identify which SKUs were sold
2. Uses a **FIFO strategy** to select which specific EPC(s) to retire (since Square doesn't know which physical item was purchased)
3. Sends retirement records to iD Cloud to keep item-level tracking accurate

> **Note on FIFO:** Without an RFID reader at checkout (like Nedap's iD POS Pro), we cannot know which exact item left the store. FIFO is the standard fallback — counts stay accurate even if the exact EPC identity is approximate. In production, the iD POS Pro at the register solves this entirely.

---

## Project Structure

```
rfid-square-sync/
├── src/
│   └── rfid_to_square_sync.py   # Core middleware logic
├── mock_data/
│   ├── rfid_scan.json           # Simulated iD Cloud RFID scan response (30 EPCs, 8 SKUs)
│   ├── square_catalog.json      # SKU ↔ Square catalog ID mapping table
│   └── sale_event.json          # Simulated Square payment.completed webhook
├── docs/
│   └── system_diagram.md        # Architecture diagram
└── README.md
```

---

## Running the Simulation

No external dependencies required — pure Python 3.

```bash
git clone https://github.com/YOUR_USERNAME/rfid-square-sync.git
cd rfid-square-sync
python src/rfid_to_square_sync.py
```

### Sample Output

```
=================================================================
  RFID → Square Inventory Sync  |  Middleware Simulation
=================================================================

  Store:      Flagship - Michigan Ave (store_042)
  Scan time:  2026-02-24T09:15:00Z
  Total EPCs scanned: 30

  SKU                     Count   Breakdown (floor / stockroom)
  ---------------------- ------   ------------------------------
  BJM-001-BLK-S               2   floor: 2
  BJM-001-BLU-L               4   floor: 2 / stockroom: 2
  BJM-001-BLU-M               3   floor: 2 / stockroom: 1
  ...

  ✅ Square updated: 14 SKU counts pushed

  Items sold in this transaction:
    • BJM-001-BLU-M  (Classic Denim Jacket)  qty: 1
    • WTS-044-WHT-S  (Linen Wrap Top)  qty: 1

  EPCs selected for retirement (FIFO strategy):
    • EPC 3034257BF400B49000001A01  →  BJM-001-BLU-M  [status: sold]
    • EPC 3034257BF400B49000001A12  →  WTS-044-WHT-S  [status: sold]

  ✅ iD Cloud updated: 2 EPC(s) marked as sold
```

---

## Key Design Decisions

**Why FIFO for EPC retirement?**
Square webhooks identify *what* was sold but not *which physical item*. Without an RFID reader at the point of sale, some heuristic is needed. FIFO is simple, auditable, and keeps counts accurate — which is the primary goal for Square sync purposes.

**Why a mapping table?**
Square and iD Cloud use different internal IDs for the same products. A dedicated SKU → Square Catalog Object ID mapping table is the cleanest solution: it's easy to maintain, easy to audit, and requires no changes to either upstream system.

**Why idempotency keys on Square payloads?**
Square's Inventory API supports idempotency keys to prevent duplicate updates if a request is retried. The key is built from `store_id + scan_timestamp`, making each sync operation safely replayable.

**What this doesn't cover (production considerations)**
- Authentication (Square OAuth, Nedap API keys)
- Retry logic and error handling for failed API calls
- Conflict resolution when scans overlap with active sales
- Delta sync vs. full physical count (full counts are safer but slower)
- iD POS Pro integration for exact EPC-at-checkout matching

---

## Context & Background

This project was built to explore the systems integration challenges between RFID-based inventory platforms and traditional POS systems — specifically the item-level vs. SKU-level translation problem that arises when connecting enterprise retail technology (Nedap iD Cloud, as deployed by Abercrombie & Fitch across ~810 stores) to small-to-mid-market POS systems like Square.

---

## Tech Stack

- Python 3.10+
- No external libraries (stdlib only: `json`, `logging`, `collections`, `pathlib`)
