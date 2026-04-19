"""Helpers for the automated Genie test runner (jobs/genie_run.py).

Trimmed copy of finance-genie/workshop/demo_utils.py, scoped to the three
after-GDS checks that genie_test.py runs. The original also contains
before-GDS variants (check_community_structure, check_merchant_overlap) and a
genie_caller convenience wrapper — none of those are used here and they would
just be dead weight on the cluster.

Exposes:
  ask_genie                    — Genie Conversation API call + result parsing
  load_ground_truth            — read ground_truth.json from a local or /Volumes path
  check_risk_score_precision   — PASS if top-20 fraud precision > 0.70
  check_community_purity       — PASS if max Louvain ring coverage > 0.80
  check_ring_pair_fraction     — PASS if same-ring fraction in returned pairs > 0.60
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
    """Submit a question to a Genie Space and return a parsed result dict.

    Returns a dict with:
      conversation_id – reuse for follow-up questions
      message_id      – ID of this message
      status          – Genie response status string
      sql             – the SQL Genie generated, or None
      df              – pandas DataFrame of query results, or None
      text            – free-text response from Genie, or None
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


def load_ground_truth(path: str) -> dict:
    """Load ground_truth.json from a local path or a /Volumes/... path."""
    with open(path) as f:
        return json.load(f)


def _ring_index_from_list(rings: list[list[int]]) -> dict[int, int]:
    """Map each account_id to the position of its ring in a plain rings list.

    Used when callers only have the raw list-of-lists form (e.g. Genie
    similarity results). The ring_id is the enumerate index.
    """
    return {int(acct): ring_idx for ring_idx, ring in enumerate(rings) for acct in ring}


def _ring_index_from_ground_truth(gt: dict) -> tuple[dict[int, int], set[int]]:
    """Return (ring_by_account, whale_ids) from a ground truth dict.

    Distinct from _ring_index_from_list because the ground truth carries an
    explicit ring_id on each ring, and also carries the whale set — both of
    which callers on this path need.
    """
    ring_by_account: dict[int, int] = {
        int(a): r["ring_id"]
        for r in gt["rings"]
        for a in r["account_ids"]
    }
    whale_ids: set[int] = {int(x) for x in gt["whale_account_ids"]}
    return ring_by_account, whale_ids


def _label_accounts(account_ids: list[int], gt: dict) -> pd.DataFrame:
    """Label account IDs as FRAUD / WHALE / NORMAL against ground truth.

    Returns a DataFrame with columns [account_id, label, ring_id].
    ring_id is populated for FRAUD accounts; None for others.
    """
    ring_by_account, whale_ids = _ring_index_from_ground_truth(gt)
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


def check_risk_score_precision(
    df: pd.DataFrame,
    gt: dict,
    topn: int = 20,
) -> dict:
    """Measure whether Genie's scored hub result surfaces fraud accounts at the top.

    Sorts df by a risk_score / score / pagerank column (whichever is present)
    descending, takes the top-N account IDs, and labels them against ground
    truth. PASSes when precision > 0.70 — confirming PageRank separates fraud
    ring members from whale accounts.

    Returns a dict with:
      precision       – fraction of top-N accounts that are fraud ring members
      true_positives  – number of fraud accounts in the top-N
      topn            – the N used (may be less if fewer rows were returned)
      passed          – True when precision > 0.70
    """
    score_col = next(
        (c for c in df.columns if any(k in c.lower() for k in ("risk", "score", "pagerank"))),
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
    labeled = _label_accounts(account_ids, gt)
    true_positives = int((labeled["label"] == "FRAUD").sum())
    precision = true_positives / actual_n if actual_n > 0 else 0.0

    return {
        "precision": precision,
        "true_positives": true_positives,
        "topn": actual_n,
        "passed": precision > 0.70,
    }


_PURITY_THRESHOLD = 0.80


def _purity_result(
    structure_type: str,
    max_ring_coverage: float,
    groups_returned: int,
    total_rows: int,
) -> dict:
    return {
        "structure_type": structure_type,
        "max_ring_coverage": max_ring_coverage,
        "groups_returned": groups_returned,
        "total_rows": total_rows,
        "passed": max_ring_coverage >= _PURITY_THRESHOLD,
    }


def _coverage_from_groups(df: pd.DataFrame, group_col: str, account_col: str, rings: list[list[int]]) -> dict:
    ring_sets = [set(int(a) for a in ring) for ring in rings]
    groups_returned = int(df[group_col].nunique())
    max_coverage = 0.0
    for _, group_df in df.groupby(group_col):
        accounts_in_group = {int(a) for a in group_df[account_col]}
        for ring_set in ring_sets:
            coverage = len(accounts_in_group & ring_set) / len(ring_set) if ring_set else 0.0
            if coverage > max_coverage:
                max_coverage = coverage
    return _purity_result("groups", max_coverage, groups_returned, len(df))


def _coverage_from_community_map(df: pd.DataFrame, group_col: str, ring_community_map: dict[str, list[int]]) -> dict:
    total_rows = len(df)
    returned_cids = {int(x) for x in df[group_col] if x is not None}
    rings_found = sum(
        1 for cids in ring_community_map.values()
        if any(int(cid) in returned_cids for cid in cids)
    )
    total_rings = len(ring_community_map)
    ring_coverage = rings_found / total_rings if total_rings > 0 else 0.0
    return _purity_result("aggregates_community_map", ring_coverage, rings_found, total_rows)


def _coverage_from_ring_candidate_flag(df: pd.DataFrame) -> dict:
    total_rows = len(df)
    ring_candidate_count = int(df["is_ring_candidate"].astype(bool).sum())
    coverage = ring_candidate_count / total_rows if total_rows > 0 else 0.0
    return _purity_result("aggregates_ring_candidate", coverage, ring_candidate_count, total_rows)


def _coverage_from_pairs(df: pd.DataFrame) -> dict:
    return _purity_result("pairs", 0.0, 0, len(df))


def check_community_purity(
    df: pd.DataFrame,
    rings: list[list[int]],
    ring_community_map: dict[str, list[int]] | None = None,
) -> dict:
    """Measure whether Genie returned pure fraud-ring community groups.

    Detects a grouping column (cluster_id / community_id / group) and an
    account column, then dispatches to one of four branches:
      * groups: group_col + account_col — covers the Louvain case with account rows
      * aggregates_community_map: group_col only, ring_community_map provided
      * aggregates_ring_candidate: group_col only, is_ring_candidate column present
      * aggregates_no_flag: group_col only, neither of the above (fails closed)
      * pairs: no group_col — coverage is undefined, returns 0.0

    Every branch returns the same shape: structure_type, max_ring_coverage,
    groups_returned, total_rows, passed. passed is True when
    max_ring_coverage >= 0.80.
    """
    group_col = next(
        (c for c in df.columns if any(k in c.lower() for k in ("cluster", "community", "group"))),
        None,
    )
    account_cols = [c for c in df.columns if "account" in c.lower()]

    if group_col and account_cols:
        return _coverage_from_groups(df, group_col, account_cols[0], rings)
    if group_col:
        if ring_community_map is not None:
            return _coverage_from_community_map(df, group_col, ring_community_map)
        if "is_ring_candidate" in df.columns:
            return _coverage_from_ring_candidate_flag(df)
        return _purity_result("aggregates_no_flag", 0.0, 0, len(df))
    return _coverage_from_pairs(df)


def check_ring_pair_fraction(
    pairs: list[tuple[int, int]],
    rings: list[list[int]],
) -> dict:
    """Measure whether Genie's similarity-ranked pairs are dominated by same-ring pairs.

    Classifies each (account_a, account_b) pair as same-ring, cross-ring, or
    unknown and reports the same-ring fraction. PASSes when the fraction
    exceeds 0.60 — confirming that Jaccard normalization in Node Similarity
    overcomes the volume-inflation problem that dominates raw shared-merchant
    counts.

    Returns a dict with:
      same_ring_fraction  – fraction of pairs where both accounts share a ring
      total_pairs         – total rows in the input
      same_ring_pairs     – pairs where both accounts are in the same ring
      cross_ring_pairs    – pairs where accounts belong to different rings
      unknown_pairs       – pairs where at least one account is not in any ring
      rings_touched       – distinct rings represented in same-ring pairs
      passed              – True when same_ring_fraction > 0.60 and total_pairs > 0
    """
    ring_by_account = _ring_index_from_list(rings)

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
