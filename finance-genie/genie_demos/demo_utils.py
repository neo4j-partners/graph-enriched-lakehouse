"""Shared utilities for finance-genie Genie demo notebooks.

Usage in a Databricks notebook:

    import sys, os
    _REPO_ROOT = os.getcwd()   # Databricks Repos sets cwd to the repo root
    _DEMO_DIR  = os.path.join(_REPO_ROOT, "finance-genie", "genie_demos")
    if _DEMO_DIR not in sys.path:
        sys.path.insert(0, _DEMO_DIR)
    from demo_utils import ask_genie, load_ground_truth, build_ring_lookup, check_community_pairs
"""

from __future__ import annotations

import json
from datetime import timedelta

import pandas as pd
from databricks.sdk import WorkspaceClient


def ask_genie(
    w: WorkspaceClient,
    space_id: str,
    question: str,
    conversation_id: str | None = None,
    timeout_seconds: int = 120,
) -> dict:
    """Submit a question to a Genie Space and return a dict with the result.

    Returns a dict with keys:
      conversation_id  – reuse this for follow-up questions
      message_id       – ID of this message
      status           – Genie response status string
      sql              – the SQL Genie generated, or None
      df               – pandas DataFrame of results, or None
      text             – text response from Genie, or None
    """
    if conversation_id:
        message = w.genie.create_message_and_wait(
            space_id=space_id,
            conversation_id=conversation_id,
            content=question,
            timeout=timedelta(seconds=timeout_seconds),
        )
    else:
        message = w.genie.start_conversation_and_wait(
            space_id=space_id,
            content=question,
            timeout=timedelta(seconds=timeout_seconds),
        )

    result = {
        "conversation_id": message.conversation_id,
        "message_id": message.id,
        "status": str(message.status.value) if message.status else "UNKNOWN",
        "sql": None,
        "df": None,
        "text": None,
    }

    if not message.attachments:
        return result

    for attachment in message.attachments:
        if attachment.text:
            result["text"] = attachment.text.content

        if attachment.query and attachment.attachment_id:
            result["sql"] = attachment.query.query
            data_result = w.genie.get_message_query_result_by_attachment(
                space_id=space_id,
                conversation_id=message.conversation_id,
                message_id=message.id,
                attachment_id=attachment.attachment_id,
            )
            sr = data_result.statement_response
            if sr and sr.manifest and sr.result:
                columns = [c.name for c in sr.manifest.schema.columns]
                rows = sr.result.data_array or []
                result["df"] = pd.DataFrame(rows, columns=columns)

    return result


def load_ground_truth(path: str) -> dict:
    """Load ground_truth.json from a local path or a /Volumes/... path."""
    with open(path) as f:
        return json.load(f)


def build_ring_lookup(gt: dict) -> tuple[dict[int, int], set[int]]:
    """Return (ring_by_account, whale_ids) from a loaded ground truth dict.

    ring_by_account maps each fraud account ID to its ring_id.
    whale_ids is the set of whale account IDs.
    """
    ring_by_account: dict[int, int] = {
        int(a): r["ring_id"]
        for r in gt["rings"]
        for a in r["account_ids"]
    }
    whale_ids: set[int] = {int(x) for x in gt["whale_account_ids"]}
    return ring_by_account, whale_ids


def check_community_pairs(
    pairs: list[tuple[int, int]],
    rings: list[list[int]],
) -> dict:
    """Measure how much ring structure Genie's pair result reveals.

    pairs   – list of (account_id_a, account_id_b) tuples from Genie's result
    rings   – list of account ID lists, one per ring (from ground_truth["rings"])

    Returns a dict with keys:
      largest_ring_footprint  – max distinct ring accounts visible in any single ring
      total_pairs             – total rows in the input
      same_ring_pairs         – pairs where both accounts share a ring
      cross_ring_pairs        – pairs where accounts belong to different rings
      unknown_pairs           – pairs where at least one account is not in any ring
      rings_touched           – number of distinct rings that appear in same-ring pairs
      passed                  – True when largest_ring_footprint <= 20 and total_pairs > 0

    Pass criterion: largest_ring_footprint <= 20.
    The check passes when Genie fails to surface a large ring footprint — confirming
    that bilateral pairs cannot reveal the 100-account community structure.
    """
    ring_by_account: dict[int, int] = {
        int(acct): ring_idx
        for ring_idx, ring in enumerate(rings)
        for acct in ring
    }

    total_pairs = len(pairs)
    same_ring = 0
    cross_ring = 0
    unknown = 0
    ring_account_sets: dict[int, set[int]] = {}

    for a, b in pairs:
        a, b = int(a), int(b)
        ra = ring_by_account.get(a)
        rb = ring_by_account.get(b)

        if ra is None or rb is None:
            unknown += 1
        elif ra == rb:
            same_ring += 1
            ring_account_sets.setdefault(ra, set()).update([a, b])
        else:
            cross_ring += 1

    largest_ring_footprint = (
        max(len(s) for s in ring_account_sets.values())
        if ring_account_sets else 0
    )

    return {
        "largest_ring_footprint": largest_ring_footprint,
        "total_pairs": total_pairs,
        "same_ring_pairs": same_ring,
        "cross_ring_pairs": cross_ring,
        "unknown_pairs": unknown,
        "rings_touched": len(ring_account_sets),
        "passed": largest_ring_footprint <= 20 and total_pairs > 0,
    }


def label_accounts(account_ids: list[int], gt: dict) -> pd.DataFrame:
    """Label account IDs against ground truth.

    Returns a DataFrame with columns [account_id, label, ring_id].
    label is 'FRAUD', 'WHALE', or 'NORMAL'.
    ring_id is populated for FRAUD accounts; None for others.
    """
    ring_by_account, whale_ids = build_ring_lookup(gt)
    rows = []
    for acct_id in account_ids:
        acct_id = int(acct_id)
        if acct_id in whale_ids:
            rows.append({"account_id": acct_id, "label": "WHALE", "ring_id": None})
        elif acct_id in ring_by_account:
            rows.append({"account_id": acct_id, "label": "FRAUD", "ring_id": ring_by_account[acct_id]})
        else:
            rows.append({"account_id": acct_id, "label": "NORMAL", "ring_id": None})
    return pd.DataFrame(rows, columns=["account_id", "label", "ring_id"])
