"""Account-level search services.

`list_risky_accounts` powers Screen 1 mode "Risky accounts".
`list_central_accounts` powers Screen 1 mode "Central accounts".
"""

from __future__ import annotations

from datetime import date, datetime

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem

from ..core._config import AppConfig
from ..models import Band, HubAccountOut, RiskAccountOut
from . import sql


def _velocity_band(txn_count_30d: int) -> Band:
    if txn_count_30d >= 50:
        return "High"
    if txn_count_30d >= 15:
        return "Medium"
    return "Low"


def _diversity_band(distinct_merchants_30d: int) -> Band:
    if distinct_merchants_30d >= 20:
        return "High"
    if distinct_merchants_30d >= 8:
        return "Medium"
    return "Low"


def _account_age_days(opened_date: object) -> int:
    if opened_date is None:
        return 0
    if isinstance(opened_date, date) and not isinstance(opened_date, datetime):
        d = opened_date
    elif isinstance(opened_date, datetime):
        d = opened_date.date()
    else:
        try:
            d = datetime.strptime(str(opened_date), "%Y-%m-%d").date()
        except ValueError:
            return 0
    return max((date.today() - d).days, 0)


def list_risky_accounts(
    ws: WorkspaceClient, config: AppConfig, limit: int = 25
) -> list[RiskAccountOut]:
    statement = f"""
        SELECT
          account_id,
          risk_score,
          COALESCE(txn_count_30d, 0) AS txn_count_30d,
          COALESCE(distinct_merchant_count_30d, 0) AS distinct_merchant_count_30d,
          opened_date
        FROM `{config.catalog}`.`{config.schema_}`.gold_accounts
        WHERE risk_score IS NOT NULL
        ORDER BY risk_score DESC
        LIMIT :row_limit
    """
    parameters = [
        StatementParameterListItem(name="row_limit", value=str(limit), type="INT"),
    ]
    rows = sql.execute(ws, config.warehouse_id, statement, parameters=parameters)

    if not rows:
        return []

    max_score = max((float(r.get("risk_score") or 0) for r in rows), default=0.0)
    normalize = max_score > 1.0

    out: list[RiskAccountOut] = []
    for r in rows:
        raw_score = float(r.get("risk_score") or 0)
        score = raw_score / max_score if normalize else raw_score
        txn_count = int(r.get("txn_count_30d") or 0)
        diversity = int(r.get("distinct_merchant_count_30d") or 0)
        out.append(
            RiskAccountOut(
                account_id=str(r.get("account_id")),
                risk_score=score,
                velocity=_velocity_band(txn_count),
                merchant_diversity=_diversity_band(diversity),
                account_age_days=_account_age_days(r.get("opened_date")),
            )
        )
    return out


def list_central_accounts(
    ws: WorkspaceClient, config: AppConfig, limit: int = 25
) -> list[HubAccountOut]:
    """Return central (high-betweenness) accounts.

    Note on `shortest_paths`: per the locked-in data contract in
    `demo-client-graph-backend.md` (Central account results section), this
    field is intentionally mocked in the web service. We derive a deterministic
    value from `inbound_transfer_events` so the output is stable across calls.
    The natural future pipeline source is All Pairs Shortest Path or closeness
    centrality.
    """
    statement = f"""
        SELECT
          account_id,
          COALESCE(betweenness_centrality, risk_score) AS betweenness,
          COALESCE(distinct_counterparty_count, 0) AS neighbors,
          COALESCE(inbound_transfer_events, 0) AS inbound_transfer_events
        FROM `{config.catalog}`.`{config.schema_}`.gold_accounts
        WHERE COALESCE(betweenness_centrality, risk_score) IS NOT NULL
        ORDER BY betweenness DESC
        LIMIT :row_limit
    """
    parameters = [
        StatementParameterListItem(name="row_limit", value=str(limit), type="INT"),
    ]
    rows = sql.execute(ws, config.warehouse_id, statement, parameters=parameters)

    if not rows:
        return []

    max_betweenness = max((float(r.get("betweenness") or 0) for r in rows), default=0.0)
    normalize = max_betweenness > 1.0

    out: list[HubAccountOut] = []
    for r in rows:
        raw_b = float(r.get("betweenness") or 0)
        betweenness = raw_b / max_betweenness if normalize else raw_b
        inbound = int(r.get("inbound_transfer_events") or 0)
        out.append(
            HubAccountOut(
                account_id=str(r.get("account_id")),
                betweenness=betweenness,
                shortest_paths=min(inbound * 5, 999),
                neighbors=int(r.get("neighbors") or 0),
            )
        )
    return out
