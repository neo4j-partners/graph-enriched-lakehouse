from databricks.sdk.service.iam import User as UserOut
from fastapi import HTTPException

from .core import Dependencies, create_router
from .models import (
    AskIn,
    AskOut,
    HubAccountOut,
    LoadIn,
    LoadOut,
    RingOut,
    RiskAccountOut,
    VersionOut,
)
from .services import accounts, genie, loader, rings

router = create_router()


@router.get("/version", response_model=VersionOut, operation_id="version")
async def version():
    return VersionOut.from_metadata()


@router.get("/current-user", response_model=UserOut, operation_id="currentUser")
def me(user_ws: Dependencies.UserClient):
    return user_ws.current_user.me()


@router.get(
    "/search/rings",
    response_model=list[RingOut],
    operation_id="searchRings",
)
def search_rings(
    ws: Dependencies.Client,
    config: Dependencies.Config,
    max_nodes: int = 500,
):
    return rings.list_rings(ws, config, max_nodes=max_nodes)


@router.get(
    "/search/risk",
    response_model=list[RiskAccountOut],
    operation_id="searchRiskAccounts",
)
def search_risk(
    ws: Dependencies.Client,
    config: Dependencies.Config,
):
    return accounts.list_risky_accounts(ws, config)


@router.get(
    "/search/hubs",
    response_model=list[HubAccountOut],
    operation_id="searchCentralAccounts",
)
def search_hubs(
    ws: Dependencies.Client,
    config: Dependencies.Config,
):
    return accounts.list_central_accounts(ws, config)


@router.post(
    "/load",
    response_model=LoadOut,
    operation_id="loadRings",
)
def load_to_lakehouse(
    body: LoadIn,
    ws: Dependencies.Client,
    config: Dependencies.Config,
):
    if not body.ring_ids:
        raise HTTPException(status_code=400, detail="ring_ids cannot be empty")
    return loader.load_rings(ws, config, body.ring_ids)


@router.post(
    "/genie/ask",
    response_model=AskOut,
    operation_id="askGenie",
)
def ask(
    body: AskIn,
    ws: Dependencies.Client,
    config: Dependencies.Config,
):
    return genie.ask_genie(ws, config, body.question, body.conversation_id)
