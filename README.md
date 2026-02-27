# SquareFlow — Square for Enterprise · Product Concept

A product discovery case study exploring how RFID inventory data can be integrated into Square's POS system to serve enterprise retail operators at scale.

---

## What This Is

This repository is a **PM portfolio project**, not a production application. It was built to stress-test a product hypothesis: that multi-location retailers using Square face structural inventory accuracy gaps that could be closed through a native RFID integration layer.

The technical artifacts — middleware simulation, mock data, and interactive prototype — exist to make the thinking tangible. They are supporting evidence for a product argument, not a proposed engineering solution.

**The hypothesis:** Multi-location retailers using Square as their POS have no reliable mechanism to keep inventory counts accurate at scale, leading to lost sales, broken customer promises, and reactive rather than proactive restocking decisions.

---

## Repository Structure

```
Inventory_Insights/
├── website/          # Interactive product concept prototype (single-file HTML)
├── src/              # Python middleware simulation
├── mock_data/        # Sample RFID scan and Square webhook payloads
└── docs/             # Supporting documentation
```

### `website/`
A single-file interactive HTML prototype demonstrating the full product concept. Navigate through five tabs:

- **About** — The problem: why Square's inventory model breaks down at enterprise retail scale, illustrated through a day-in-the-life story of a store manager
- **Discovery** — Product thinking: problem statement, who I'd interview, hypothesis, success metrics, and open questions
- **Integration** — Architecture walkthrough: how an RFID tag on a garment becomes an accurate inventory count in Square, step by step
- **Metrics** — The risk scoring model: how sell velocity, stock depletion, and lead time are combined into a 0–100 stockout risk score
- **Demo** — Live interactive dashboard: 14 SKUs with real-time AI risk scoring, a what-if simulator, and an AI reasoning panel

### `src/`
Python simulation of the SquareFlow middleware layer. Demonstrates two sync flows:
- **RFID → Square:** Reads EPC scan data from iD Cloud, aggregates individual item records into SKU counts, and pushes inventory updates to Square's API
- **Square → iD Cloud:** Receives sale webhook events from Square and retires the corresponding RFID tags in the item database using FIFO logic

### `mock_data/`
Sample JSON payloads used by the middleware simulation:
- `rfid_scan.json` — 30 individual item records with EPCs, SKU codes, and location status (floor vs. stockroom)
- `sale_event.json` — Square `payment.completed` webhook payload with line items and quantities
- `square_catalog.json` — Mapping table translating internal SKU codes to Square's `catalog_object_id` values

---

## The Product Concept

### Five Enterprise Retail Needs

Current Square inventory management works well at small scale. At 10–200 locations, retailers need:

1. **Item-level visibility** — tracking individual garments, not just product totals
2. **Self-correcting accuracy** — continuous RFID sync that closes the gap between physical reality and system records
3. **Zone awareness** — knowing whether stock is on the floor or in the stockroom, enabling reliable BOPIS
4. **Cross-location intelligence** — surfacing transfer opportunities and "available nearby" without manual work
5. **Predictive restocking** — moving from reactive (stockout discovered at 0 units) to proactive (risk flagged at 3 units)

### The Risk Model

The prototype uses a weighted scoring model:

```
Risk Score = (Sell Velocity × 0.45) + (Stock Depletion × 0.35) + (Lead Time Pressure × 0.20)
```

Scores 0–100 map to four action states: **Healthy** → **Monitor** → **Elevated** → **Critical / Reorder Now**

### Architecture at a Glance

```
RFID Tag → Handheld Scanner → Nedap iD Cloud → SquareFlow Middleware → Square POS
                                                        ↑
                                             EPC aggregation · AI risk scoring · Catalog mapping
```

---

## What I'd Do Before Building This

The prototype was built to make a hypothesis concrete — not to propose shipping it. Before any real product work, the next steps would be:

- **5 customer interviews** with store operations managers at 15–50 location Square retailers to validate whether inventory sync accuracy or predictive restocking is the higher-priority pain
- **1 internal conversation** with a Square mid-market account manager to understand whether this is a known churn driver
- **Hypothesis validation:** I believe sync accuracy is the prerequisite — AI recommendations have no credibility until baseline counts are trusted

**Open questions:**
- Would Square build this natively, or is there a partner/integration opportunity?
- Is the pain acute enough to justify RFID infrastructure investment for sub-50-store operators?
- Who owns the buying decision — store operations or IT?

---

## Tech Stack

- **Prototype:** Vanilla HTML/CSS/JavaScript — single file, no dependencies, deployable to GitHub Pages
- **Middleware simulation:** Python 3
- **Mock data:** JSON (simulates Nedap iD Cloud API responses and Square webhook payloads)

---

## Running the Prototype

No build step required. Open `website/index.html` directly in any browser, or deploy to GitHub Pages.

## Running the Middleware Simulation

```bash
cd src
python3 rfid_to_square_sync.py
```

Requires Python 3.7+. No external dependencies.

---

*Product Discovery Case Study · RFID ↔ Square Inventory Sync*
