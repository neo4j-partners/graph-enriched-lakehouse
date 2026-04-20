"""Shared utilities for finance-genie Genie demo notebooks.

Usage in a Databricks notebook:

    import sys, os
    _REPO_ROOT = os.getcwd()   # Databricks Repos sets cwd to the repo root
    _DEMO_DIR  = os.path.join(_REPO_ROOT, "finance-genie", "workshop")
    if _DEMO_DIR not in sys.path:
        sys.path.insert(0, _DEMO_DIR)
    from demo_utils import (
        genie_caller, load_ground_truth, build_ring_lookup,
        check_community_structure, check_merchant_overlap,
        check_risk_score_precision, check_community_purity, check_ring_pair_fraction,
    )
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
        "message_id": message.message_id,
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
            data_result = w.genie.get_message_attachment_query_result(
                space_id=space_id,
                conversation_id=message.conversation_id,
                message_id=message.message_id,
                attachment_id=attachment.attachment_id,
            )
            sr = data_result.statement_response
            if sr and sr.manifest and sr.result:
                columns = [c.name for c in sr.manifest.schema.columns]
                rows = sr.result.data_array or []
                result["df"] = pd.DataFrame(rows, columns=columns)

    return result


def genie_caller(w: WorkspaceClient, space_id: str):
    """Return a bound ask_genie function for a specific workspace and space.

    Usage::

        ask_genie = genie_caller(w, SPACE_ID)
        response  = ask_genie("Which accounts have the highest risk score?")

    The returned callable has the same signature as ask_genie minus the first
    two positional arguments (w and space_id).
    """
    def ask(
        question: str,
        conversation_id: str | None = None,
        timeout_seconds: int = 120,
    ) -> dict:
        return ask_genie(w, space_id, question, conversation_id, timeout_seconds)

    return ask


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


def check_community_structure(
    df: "pd.DataFrame",
    rings: list[list[int]],
) -> dict:
    """Measure whether Genie's result contains community grouping structure.

    Accepts whatever DataFrame Genie returned and determines whether it
    contains groups (a cluster or community column) or only pairs (two
    account columns with no grouping).

    df    – pandas DataFrame from Genie's result
    rings – list of account ID lists, one per ring (from ground_truth["rings"])

    Returns a dict with keys:
      structure_type     – 'groups' if a grouping column was found, 'pairs' otherwise
      max_ring_coverage  – max fraction of any ring covered by a single identified group;
                           0.0 when Genie returned only pairs
      groups_returned    – number of distinct groups Genie identified (0 for pairs)
      total_rows         – total rows in the result
      passed             – True when max_ring_coverage < 0.50

    Pass criterion: max_ring_coverage < 0.50.
    The check passes when Genie cannot form a group covering more than half of any
    fraud ring — confirming that SQL bilateral pairs cannot replicate Louvain
    community detection. When Genie returns only pairs, max_ring_coverage is 0.0
    and the check always passes, which is the correct result: Genie identified
    no communities at all.
    """
    ring_sets = [set(int(a) for a in ring) for ring in rings]
    ring_size = len(ring_sets[0]) if ring_sets else 0

    # Detect a grouping column (cluster_id, community_id, group, etc.)
    group_col = next(
        (c for c in df.columns if any(kw in c.lower() for kw in ("cluster", "community", "group"))),
        None,
    )
    account_cols = [c for c in df.columns if "account" in c.lower()]

    if group_col and account_cols:
        structure_type = "groups"
        account_col = account_cols[0]
        groups_returned = int(df[group_col].nunique())
        max_coverage = 0.0

        for _, group_df in df.groupby(group_col):
            accounts_in_group = {int(a) for a in group_df[account_col]}
            for ring_set in ring_sets:
                coverage = len(accounts_in_group & ring_set) / ring_size if ring_size > 0 else 0.0
                if coverage > max_coverage:
                    max_coverage = coverage
    else:
        # Genie returned only pairs — no community grouping structure present
        structure_type = "pairs"
        max_coverage = 0.0
        groups_returned = 0

    return {
        "structure_type": structure_type,
        "max_ring_coverage": max_coverage,
        "groups_returned": groups_returned,
        "total_rows": len(df),
        "passed": max_coverage < 0.50,
    }


def check_merchant_overlap(
    pairs: list[tuple[int, int]],
    rings: list[list[int]],
) -> dict:
    """Measure how much ring structure Genie's shared-merchant pairs reveal.

    pairs  – list of (account_id_a, account_id_b) tuples from Genie's result
    rings  – list of account ID lists, one per ring (from ground_truth["rings"])

    Returns a dict with keys:
      same_ring_fraction  – fraction of pairs where both accounts share a ring
      total_pairs         – total rows in the input
      same_ring_pairs     – pairs where both accounts are in the same ring
      cross_ring_pairs    – pairs where accounts belong to different rings
      unknown_pairs       – pairs where at least one account is not in any ring
      rings_touched       – number of distinct rings that appear in same-ring pairs
      passed              – True when same_ring_fraction < 0.30 and total_pairs > 0

    Pass criterion: same_ring_fraction < 0.30.
    The check passes when Genie fails to surface ring pairs — confirming that raw
    shared-merchant count is dominated by high-volume normal accounts rather than
    ring members with elevated anchor-merchant overlap.
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
    rings_seen: set[int] = set()

    for a, b in pairs:
        a, b = int(a), int(b)
        ra = ring_by_account.get(a)
        rb = ring_by_account.get(b)

        if ra is None or rb is None:
            unknown += 1
        elif ra == rb:
            same_ring += 1
            rings_seen.add(ra)
        else:
            cross_ring += 1

    same_ring_fraction = same_ring / total_pairs if total_pairs > 0 else 0.0

    return {
        "same_ring_fraction": same_ring_fraction,
        "total_pairs": total_pairs,
        "same_ring_pairs": same_ring,
        "cross_ring_pairs": cross_ring,
        "unknown_pairs": unknown,
        "rings_touched": len(rings_seen),
        "passed": same_ring_fraction < 0.30 and total_pairs > 0,
    }


def check_risk_score_precision(
    df: "pd.DataFrame",
    gt: dict,
    topn: int = 20,
) -> dict:
    """Measure whether Genie's scored hub result surfaces fraud accounts at the top.

    Expects a DataFrame with a risk_score column and an account_id column.
    Sorts by risk_score descending, takes the top topn accounts, and checks
    how many are fraud ring members.

    df    – pandas DataFrame from Genie's result (must include a score column)
    gt    – full ground truth dict (passed to label_accounts)
    topn  – number of top accounts to evaluate (default 20)

    Returns a dict with keys:
      precision       – fraction of top-N accounts that are fraud ring members
      true_positives  – number of fraud accounts in the top-N
      topn            – the N used (may be less if fewer rows returned)
      passed          – True when precision > 0.70

    Pass criterion: precision > 0.70.
    The check passes when GDS-enriched risk_score puts fraud ring members at the
    top of the list, confirming PageRank separates fraud from whale accounts.
    """
    score_col = next(
        (c for c in df.columns if "risk" in c.lower() or "score" in c.lower() or "pagerank" in c.lower()),
        None,
    )
    id_col = next(
        (c for c in df.columns if "account_id" in c.lower()),
        df.columns[0],
    )

    sorted_df = df.sort_values(score_col, ascending=False) if score_col else df
    top_df = sorted_df.head(topn)
    actual_n = len(top_df)
    account_ids = top_df[id_col].astype(int).tolist()
    labeled = label_accounts(account_ids, gt)
    true_positives = int((labeled["label"] == "FRAUD").sum())
    precision = true_positives / actual_n if actual_n > 0 else 0.0

    return {
        "precision": precision,
        "true_positives": true_positives,
        "topn": actual_n,
        "passed": precision > 0.70,
    }


def check_community_purity(
    df: "pd.DataFrame",
    rings: list[list[int]],
) -> dict:
    """Measure whether Genie's community result returns pure fraud ring groups.

    Uses the same grouping-column detection as check_community_structure but
    applies the opposite pass criterion: after GDS enrichment, groups should
    cover most of each ring rather than fragmenting them into bilateral pairs.

    df    – pandas DataFrame from Genie's result
    rings – list of account ID lists, one per ring (from ground_truth["rings"])

    Returns a dict with keys:
      structure_type     – 'groups' if a grouping column was found, 'pairs' otherwise
      max_ring_coverage  – max fraction of any ring covered by a single identified group
      groups_returned    – number of distinct groups Genie identified
      total_rows         – total rows in the result
      passed             – True when max_ring_coverage > 0.80

    Pass criterion: max_ring_coverage > 0.80.
    The check passes when Genie, using community_id from Louvain, returns groups
    that cover at least 80% of a fraud ring — confirming that community detection
    preserves ring structure rather than fragmenting it into bilateral pairs.
    """
    ring_sets = [set(int(a) for a in ring) for ring in rings]
    ring_size = len(ring_sets[0]) if ring_sets else 0

    group_col = next(
        (c for c in df.columns if any(kw in c.lower() for kw in ("cluster", "community", "group"))),
        None,
    )
    account_cols = [c for c in df.columns if "account" in c.lower()]

    if group_col and account_cols:
        structure_type = "groups"
        account_col = account_cols[0]
        groups_returned = int(df[group_col].nunique())
        max_coverage = 0.0

        for _, group_df in df.groupby(group_col):
            accounts_in_group = {int(a) for a in group_df[account_col]}
            for ring_set in ring_sets:
                coverage = len(accounts_in_group & ring_set) / ring_size if ring_size > 0 else 0.0
                if coverage > max_coverage:
                    max_coverage = coverage
    else:
        structure_type = "pairs"
        max_coverage = 0.0
        groups_returned = 0

    return {
        "structure_type": structure_type,
        "max_ring_coverage": max_coverage,
        "groups_returned": groups_returned,
        "total_rows": len(df),
        "passed": max_coverage > 0.80,
    }


def check_ring_pair_fraction(
    pairs: list[tuple[int, int]],
    rings: list[list[int]],
) -> dict:
    """Measure whether Genie's similarity-ranked pairs surface same-ring account pairs.

    Uses the same pair-classification logic as check_merchant_overlap but
    applies the opposite pass criterion: after GDS enrichment, same-ring pairs
    should dominate the top results rather than high-volume normal accounts.

    pairs  – list of (account_id_a, account_id_b) tuples from Genie's result
    rings  – list of account ID lists, one per ring (from ground_truth["rings"])

    Returns a dict with keys:
      same_ring_fraction  – fraction of pairs where both accounts share a ring
      total_pairs         – total rows in the input
      same_ring_pairs     – pairs where both accounts are in the same ring
      cross_ring_pairs    – pairs where accounts belong to different rings
      unknown_pairs       – pairs where at least one account is not in any ring
      rings_touched       – number of distinct rings that appear in same-ring pairs
      passed              – True when same_ring_fraction > 0.60 and total_pairs > 0

    Pass criterion: same_ring_fraction > 0.60.
    The check passes when Genie, using similarity_score from Node Similarity,
    returns pairs where at least 60% are same-ring account pairs — confirming
    that Jaccard normalization overcomes the volume inflation problem.
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
    rings_seen: set[int] = set()

    for a, b in pairs:
        a, b = int(a), int(b)
        ra = ring_by_account.get(a)
        rb = ring_by_account.get(b)

        if ra is None or rb is None:
            unknown += 1
        elif ra == rb:
            same_ring += 1
            rings_seen.add(ra)
        else:
            cross_ring += 1

    same_ring_fraction = same_ring / total_pairs if total_pairs > 0 else 0.0

    return {
        "same_ring_fraction": same_ring_fraction,
        "total_pairs": total_pairs,
        "same_ring_pairs": same_ring,
        "cross_ring_pairs": cross_ring,
        "unknown_pairs": unknown,
        "rings_touched": len(rings_seen),
        "passed": same_ring_fraction > 0.60 and total_pairs >= 5,
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
