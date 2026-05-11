"""Mosaic AI multi-agent supervisor for the Agentic Commerce assistant (STUB).

STATUS
    Skeleton only. Not deployed. The
    retail-agent-deploy-supervisor entry point prints a STUB message
    and exits without calling agents.deploy().

DESIGN
    docs/agentic-commerce.md describes a two-agent system. A Databricks
    Mosaic AI multi-agent supervisor classifies each user message and routes:

      Analytics questions       -> Genie space over the lakehouse Delta tables
      Product / KG questions    -> the deployed retail KG agent endpoint
      Combined questions        -> both, with a synthesized response

    The supervisor itself is logged to MLflow as a ChatAgent and deployed to
    a separate Model Serving endpoint, in addition to the existing KG agent
    endpoint deployed by retail-agent-deploy.

TODO TO MAKE THIS REAL
    1. Provision a Genie space over retail_assistant.retail.{transactions,
       customers, reviews, inventory_snapshots, stores}. Set
       CONFIG.genie_space_id in retail_agent.agent.config.
    2. Replace build_supervisor_chat_agent() with an implementation that
       uses databricks_ai_bridge.GenieAgent plus the multi-agent supervisor
       pattern from the databricks-agents docs.
    3. Wire retail_agent/deployment/deploy_supervisor.py to log/register/deploy
       this agent, mirroring retail_agent/deployment/deploy_agent.py.
    4. Add a demo entry point that exercises analytics,
       KG, and combined queries against the supervisor endpoint.
"""

from dataclasses import dataclass


@dataclass
class SubAgentSpec:
    """One sub-agent the supervisor can route to."""

    name: str
    description: str
    endpoint_or_space: str  # KG endpoint name OR Genie space id, set at deploy time


KG_AGENT = SubAgentSpec(
    name="retail_kg_agent",
    description=(
        "Answers product, recommendation, and support questions using the "
        "Neo4j knowledge graph and GraphRAG retrieval. Best for: product "
        "search, related products, troubleshooting, support diagnostics."
    ),
    endpoint_or_space="",  # TODO: CONFIG.resolved_endpoint_name at deploy time
)

GENIE_AGENT = SubAgentSpec(
    name="retail_lakehouse_genie",
    description=(
        "Answers analytics questions over the retail lakehouse using "
        "Databricks Genie. Best for: revenue trends, customer segments, "
        "basket analysis, time-series queries over Delta tables."
    ),
    endpoint_or_space="",  # TODO: CONFIG.genie_space_id at deploy time
)


def build_supervisor_chat_agent():
    """Build the Mosaic AI multi-agent supervisor as an MLflow ChatAgent.

    Not yet implemented. See module docstring for the TODOs required.
    """
    raise NotImplementedError(
        "Supervisor agent is not yet implemented. See "
        "retail_agent.agent.supervisor module docstring for TODOs."
    )
