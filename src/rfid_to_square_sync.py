"""
rfid_to_square_sync.py
----------------------
Middleware that translates Nedap iD Cloud RFID item-level scan data
into Square SKU-level inventory updates.

Demonstrates the core translation layer between:
  - iD Cloud: tracks individual items by unique EPC
  - Square:   tracks inventory counts by SKU

Author: Portfolio Project — RFID ↔ POS Inventory Sync
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup — structured output so results are easy to read in terminal
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths to mock data
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
RFID_SCAN_PATH    = BASE_DIR / "mock_data" / "rfid_scan.json"
CATALOG_PATH      = BASE_DIR / "mock_data" / "square_catalog.json"
SALE_EVENT_PATH   = BASE_DIR / "mock_data" / "sale_event.json"


# ===========================================================================
# STEP 1 — Load mock data
# ===========================================================================

def load_json(path: Path) -> dict:
    """Load and return a JSON file."""
    with open(path) as f:
        return json.load(f)


# ===========================================================================
# STEP 2 — Aggregate EPCs by SKU (the core translation logic)
# ===========================================================================

def aggregate_epcs_by_sku(scan_data: dict) -> dict[str, list[str]]:
    """
    iD Cloud returns a flat list of individual RFID items (EPCs).
    This function groups them by SKU so Square can understand the count.

    Returns:
        { "BJM-001-BLU-M": ["epc1", "epc2", ...], ... }
    """
    sku_to_epcs = defaultdict(list)

    for item in scan_data["items"]:
        if item["status"] == "in_store":
            sku_to_epcs[item["sku"]].append(item["epc"])

    return dict(sku_to_epcs)


def get_zone_breakdown(scan_data: dict, sku: str) -> dict[str, int]:
    """
    Bonus insight: break down stock count by zone (floor vs stockroom).
    Useful for replenishment decisions — hidden from Square but valuable internally.
    """
    zones = defaultdict(int)
    for item in scan_data["items"]:
        if item["sku"] == sku and item["status"] == "in_store":
            zones[item["zone"]] += 1
    return dict(zones)


# ===========================================================================
# STEP 3 — Build Square Inventory API payload
# ===========================================================================

def build_square_inventory_payload(
    sku_counts: dict[str, int],
    catalog: dict,
    store_id: str,
    occurred_at: str
) -> dict:
    """
    Constructs the payload for Square's POST /v2/inventory/changes endpoint.

    Square expects a PHYSICAL_COUNT change per SKU per location.
    We translate our SKU counts into that format using the catalog mapping.
    """
    location_id = catalog["location_map"][store_id]["square_location_id"]
    changes = []
    unmapped_skus = []

    for sku, count in sku_counts.items():
        if sku not in catalog["sku_map"]:
            unmapped_skus.append(sku)
            continue

        square_obj_id = catalog["sku_map"][sku]["square_catalog_object_id"]

        changes.append({
            "type": "PHYSICAL_COUNT",
            "physical_count": {
                "catalog_object_id": square_obj_id,
                "location_id": location_id,
                "quantity": str(count),
                "occurred_at": occurred_at
            }
        })

    if unmapped_skus:
        log.warning(f"  ⚠️  {len(unmapped_skus)} SKU(s) not found in catalog map: {unmapped_skus}")

    return {
        "idempotency_key": f"sync_{store_id}_{occurred_at}",
        "changes": changes
    }


# ===========================================================================
# STEP 4 — Handle a Square sale webhook (sale → retire an EPC in iD Cloud)
# ===========================================================================

def process_sale_event(sale_event: dict, sku_to_epcs: dict[str, list[str]]) -> list[dict]:
    """
    When Square fires a payment.completed webhook, we need to mark an EPC
    as 'sold' in iD Cloud for each line item.

    Since Square doesn't know WHICH physical item was sold (only the SKU),
    we use a FIFO strategy: retire the first available EPC for that SKU.

    Returns a list of iD Cloud EPC retirement records.
    """
    retirement_records = []
    line_items = sale_event["data"]["object"]["payment"]["line_items"]

    for line_item in line_items:
        sku = line_item["sku"]
        qty_sold = int(line_item["quantity"])

        if sku not in sku_to_epcs or len(sku_to_epcs[sku]) == 0:
            log.warning(f"  ⚠️  SKU {sku} sold but no EPCs found in current scan data.")
            continue

        for _ in range(qty_sold):
            if not sku_to_epcs[sku]:
                log.warning(f"  ⚠️  Sold more units of {sku} than EPCs available.")
                break

            # FIFO: pop the first EPC from the list
            retired_epc = sku_to_epcs[sku].pop(0)

            retirement_records.append({
                "epc": retired_epc,
                "sku": sku,
                "status": "sold",
                "sold_at": sale_event["data"]["object"]["payment"].get("created_at",
                           datetime.now(timezone.utc).isoformat()),
                "square_order_id": sale_event["data"]["object"]["payment"]["order_id"]
            })

    return retirement_records


# ===========================================================================
# STEP 5 — Mock API "send" functions (simulate HTTP calls)
# ===========================================================================

def mock_send_to_square(payload: dict) -> dict:
    """
    Simulates POST /v2/inventory/changes to Square's API.
    In production, this would be an authenticated requests.post() call.
    """
    return {
        "success": True,
        "counts_updated": len(payload["changes"]),
        "idempotency_key": payload["idempotency_key"],
        "simulated_response": "200 OK"
    }


def mock_send_to_id_cloud(retirement_records: list[dict]) -> dict:
    """
    Simulates PATCH /epcs/status to Nedap iD Cloud's API.
    In production, this would update each EPC's status to 'sold'.
    """
    return {
        "success": True,
        "epcs_retired": len(retirement_records),
        "simulated_response": "200 OK"
    }


# ===========================================================================
# MAIN — Run the full sync simulation
# ===========================================================================

def main():
    print("\n" + "="*65)
    print("  RFID → Square Inventory Sync  |  Middleware Simulation")
    print("="*65 + "\n")

    # --- Load data ---
    log.info("Loading mock data files...")
    scan_data  = load_json(RFID_SCAN_PATH)
    catalog    = load_json(CATALOG_PATH)
    sale_event = load_json(SALE_EVENT_PATH)

    store_id        = scan_data["store_id"]
    store_name      = scan_data["store_name"]
    scan_timestamp  = scan_data["scan_timestamp"]

    print(f"  Store:      {store_name} ({store_id})")
    print(f"  Scan time:  {scan_timestamp}")
    print(f"  Total EPCs scanned: {len(scan_data['items'])}\n")

    # -----------------------------------------------------------------------
    # FLOW A: RFID Scan → Aggregate → Push to Square
    # -----------------------------------------------------------------------
    print("-"*65)
    print("  FLOW A: iD Cloud Scan → Square Inventory Update")
    print("-"*65)

    log.info("Aggregating EPCs by SKU...")
    sku_to_epcs = aggregate_epcs_by_sku(scan_data)

    print(f"\n  {'SKU':<22} {'Count':>6}   {'Breakdown (floor / stockroom)'}")
    print(f"  {'-'*22} {'------':>6}   {'-'*30}")

    sku_counts = {}
    for sku, epcs in sorted(sku_to_epcs.items()):
        count = len(epcs)
        sku_counts[sku] = count
        zones = get_zone_breakdown(scan_data, sku)
        zone_str = " / ".join(f"{z}: {n}" for z, n in zones.items())
        product = catalog["sku_map"].get(sku, {}).get("product_name", "Unknown")
        print(f"  {sku:<22} {count:>6}   {zone_str}  ({product})")

    log.info("\nBuilding Square inventory payload...")
    square_payload = build_square_inventory_payload(
        sku_counts, catalog, store_id, scan_timestamp
    )

    log.info("Sending to Square Inventory API (mock)...")
    square_response = mock_send_to_square(square_payload)

    print(f"\n  ✅ Square updated: {square_response['counts_updated']} SKU counts pushed")
    print(f"     Idempotency key: {square_response['idempotency_key']}")

    # -----------------------------------------------------------------------
    # FLOW B: Square Sale Webhook → Retire EPCs in iD Cloud
    # -----------------------------------------------------------------------
    print(f"\n{'-'*65}")
    print("  FLOW B: Square Sale Webhook → iD Cloud EPC Retirement")
    print("-"*65)

    log.info(f"Processing sale event: {sale_event['event_id']}")
    line_items = sale_event["data"]["object"]["payment"]["line_items"]

    print(f"\n  Items sold in this transaction:")
    for item in line_items:
        product = catalog["sku_map"].get(item["sku"], {}).get("product_name", "Unknown")
        print(f"    • {item['sku']}  ({product})  qty: {item['quantity']}")

    retirement_records = process_sale_event(sale_event, sku_to_epcs)

    print(f"\n  EPCs selected for retirement (FIFO strategy):")
    for r in retirement_records:
        print(f"    • EPC {r['epc']}  →  {r['sku']}  [status: {r['status']}]")

    log.info("Sending EPC retirements to iD Cloud (mock)...")
    id_cloud_response = mock_send_to_id_cloud(retirement_records)

    print(f"\n  ✅ iD Cloud updated: {id_cloud_response['epcs_retired']} EPC(s) marked as sold")

    # -----------------------------------------------------------------------
    # Post-sale inventory snapshot
    # -----------------------------------------------------------------------
    print(f"\n{'-'*65}")
    print("  POST-SALE INVENTORY SNAPSHOT (updated counts after sale)")
    print("-"*65)

    print(f"\n  {'SKU':<22} {'Before':>8} {'After':>8}")
    print(f"  {'-'*22} {'------':>8} {'-----':>8}")

    sold_skus = {item["sku"]: int(item["quantity"]) for item in line_items}
    for sku in sorted(sku_counts.keys()):
        before = sku_counts[sku]
        after = len(sku_to_epcs.get(sku, []))
        flag = " ← sold" if sku in sold_skus else ""
        print(f"  {sku:<22} {before:>8} {after:>8}{flag}")

    print("\n" + "="*65)
    print("  Sync simulation complete.")
    print("="*65 + "\n")


if __name__ == "__main__":
    main()
