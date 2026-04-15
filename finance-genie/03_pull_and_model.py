# Databricks notebook source
# MAGIC %md
# MAGIC # Graph-Augmented Intelligence — Webinar
# MAGIC ## Notebook 03: Pull Graph Features & Quantify ML Lift
# MAGIC
# MAGIC Now that GDS algorithms have been executed in **Neo4j Aura** (via `02_aura_gds_guide`),
# MAGIC every Account node carries three new properties:
# MAGIC
# MAGIC | Property | Algorithm | Fraud Signal |
# MAGIC |----------|-----------|-------------|
# MAGIC | `risk_score` | PageRank | Central accounts in money-flow networks |
# MAGIC | `community_id` | Louvain | Tightly connected clusters (fraud rings) |
# MAGIC | `similarity_score` | Node Similarity | Accounts sharing the same merchants |
# MAGIC
# MAGIC This notebook closes the loop:
# MAGIC
# MAGIC ```
# MAGIC Neo4j Aura ──► Spark Connector ──► Delta Lake ──► Feature Store
# MAGIC                                                        │
# MAGIC                               Baseline Model ◄── Training Table ──► Graph-Augmented Model
# MAGIC ```
# MAGIC
# MAGIC We train **two models** on the same fraud-detection task and measure the lift
# MAGIC that graph features provide.

# COMMAND ----------

# MAGIC %md ## 0. Configuration

# COMMAND ----------

CATALOG = "graph_feature_engineering_demo"
SCHEMA  = "neo4j_webinar"

NEO4J_URI      = dbutils.secrets.get("neo4j-graph-engineering", "uri")
NEO4J_USER     = dbutils.secrets.get("neo4j-graph-engineering", "username")
NEO4J_PASSWORD = dbutils.secrets.get("neo4j-graph-engineering", "password")

NEO4J_OPTS = {
    "url":                    NEO4J_URI,
    "authentication.basic.username": NEO4J_USER,
    "authentication.basic.password": NEO4J_PASSWORD,
}

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

# MAGIC %md ---
# MAGIC ## 1. Read Graph Features from Neo4j
# MAGIC
# MAGIC The Spark Connector reads the enriched Account nodes directly — all three
# MAGIC GDS-computed properties come along as columns.

# COMMAND ----------

graph_features_df = (
    spark.read
    .format("org.neo4j.spark.DataSource")
    .options(**NEO4J_OPTS)
    .option("labels", "Account")
    .load()
    .select(
        F.col("account_id").cast("int"),
        F.col("risk_score").cast("double"),
        F.col("community_id").cast("long"),
        F.col("similarity_score").cast("double"),
    )
)

print(f"Read {graph_features_df.count()} Account nodes with graph features")
graph_features_df.show(10)

# COMMAND ----------

# MAGIC %md ## 2. Write Graph Features to Delta

# COMMAND ----------

FEATURES_TABLE = f"{CATALOG}.{SCHEMA}.account_graph_features"

# Ensure account_id is NOT NULL so it can serve as a primary key
spark.sql(f"DROP TABLE IF EXISTS {FEATURES_TABLE}")

spark.sql(f"""
    CREATE TABLE {FEATURES_TABLE} (
        account_id     INT          NOT NULL,
        risk_score     DOUBLE,
        community_id   BIGINT,
        similarity_score DOUBLE,
        CONSTRAINT account_graph_features_pk PRIMARY KEY (account_id)
    )
""")

graph_features_df.writeTo(FEATURES_TABLE).append()

print(f"Written to {FEATURES_TABLE} (with PK constraint)")

# COMMAND ----------

# MAGIC %md ## 3. Register in Feature Store (Unity Catalog)
# MAGIC
# MAGIC Makes graph features discoverable and joinable with any training dataset
# MAGIC by `account_id`.

# COMMAND ----------

from databricks.feature_engineering import FeatureEngineeringClient

fe = FeatureEngineeringClient()

# Read back from Delta (not the Neo4j source) to avoid Spark V2 push-down issues
graph_features_delta = spark.table(FEATURES_TABLE)

fe.write_table(
    name=FEATURES_TABLE,
    df=graph_features_delta,
    mode="merge",
)

print(f"Feature Store updated: {graph_features_delta.count()} rows")

# COMMAND ----------

# MAGIC %md ---
# MAGIC ## 4. Build the Full Training Table
# MAGIC
# MAGIC Join original tabular features with graph-derived features to create
# MAGIC the complete training dataset.

# COMMAND ----------

accounts_df = spark.table(f"{CATALOG}.{SCHEMA}.accounts")
graph_feat  = spark.table(FEATURES_TABLE)

# Tabular features from transactions
txn_features = (
    spark.table(f"{CATALOG}.{SCHEMA}.transactions")
    .groupBy("account_id")
    .agg(
        F.count("*").alias("txn_count"),
        F.round(F.avg("amount"), 2).alias("avg_txn_amount"),
        F.round(F.stddev("amount"), 2).alias("std_txn_amount"),
        F.round(F.max("amount"), 2).alias("max_txn_amount"),
        F.countDistinct("merchant_id").alias("unique_merchants"),
        F.round(F.avg("txn_hour").cast("double"), 2).alias("avg_txn_hour"),
        F.round(F.sum(F.when(F.col("txn_hour").between(0, 5), 1).otherwise(0)) / F.count("*"), 4)
            .alias("night_txn_ratio"),
    )
)

# P2P transfer features
p2p_features = (
    spark.table(f"{CATALOG}.{SCHEMA}.account_links")
    .groupBy(F.col("src_account_id").alias("account_id"))
    .agg(
        F.count("*").alias("p2p_out_count"),
        F.round(F.avg("amount"), 2).alias("avg_p2p_amount"),
    )
)

# Full training table
training_df = (
    accounts_df
    .join(txn_features,  "account_id", "left")
    .join(p2p_features,  "account_id", "left")
    .join(graph_feat,    "account_id", "left")
    .fillna(0)
)

TRAINING_TABLE = f"{CATALOG}.{SCHEMA}.training_dataset"
(training_df
 .write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true")
 .saveAsTable(TRAINING_TABLE)
)

print(f"Training table: {training_df.count()} rows, {len(training_df.columns)} columns")
training_df.printSchema()

# COMMAND ----------

# MAGIC %md ## 5. Preview — Feature Correlations with Fraud

# COMMAND ----------

display(
    training_df
    .groupBy("is_fraud")
    .agg(
        F.round(F.avg("risk_score"), 6).alias("avg_risk_score"),
        F.round(F.avg("similarity_score"), 4).alias("avg_similarity"),
        F.round(F.avg("txn_count"), 1).alias("avg_txn_count"),
        F.round(F.avg("unique_merchants"), 1).alias("avg_unique_merchants"),
        F.round(F.avg("night_txn_ratio"), 4).alias("avg_night_ratio"),
        F.round(F.avg("p2p_out_count"), 1).alias("avg_p2p_out"),
    )
)

# COMMAND ----------

# MAGIC %md ---
# MAGIC ## 6. Prepare Data for Modelling

# COMMAND ----------

import mlflow
import mlflow.sklearn
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

mlflow.set_experiment(f"/Workspace/Users/{dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()}/graph_augmented_fraud")

# COMMAND ----------

pdf = training_df.toPandas()

# Define feature sets
TABULAR_FEATURES = [
    "balance", "holder_age",
    "txn_count", "avg_txn_amount", "std_txn_amount", "max_txn_amount",
    "unique_merchants", "avg_txn_hour", "night_txn_ratio",
    "p2p_out_count", "avg_p2p_amount",
]

GRAPH_FEATURES = [
    "risk_score",
    "community_id",
    "similarity_score",
]

ALL_FEATURES = TABULAR_FEATURES + GRAPH_FEATURES
LABEL = "is_fraud"

# Clean
pdf = pdf.fillna(0)
pdf["is_fraud"] = pdf["is_fraud"].astype(int)

# Encode categoricals as ordinals for the demo
pdf["account_type_enc"] = pdf["account_type"].astype("category").cat.codes
pdf["region_enc"]       = pdf["region"].astype("category").cat.codes
TABULAR_FEATURES += ["account_type_enc", "region_enc"]
ALL_FEATURES     += ["account_type_enc", "region_enc"]

# Split
X_train, X_test, y_train, y_test = train_test_split(
    pdf[ALL_FEATURES], pdf[LABEL], test_size=0.2, random_state=42, stratify=pdf[LABEL]
)

print(f"Train: {len(X_train)} | Test: {len(X_test)}")
print(f"Fraud rate (train): {y_train.mean():.3f}")

# COMMAND ----------

# MAGIC %md ---
# MAGIC ## 7. Train Baseline Model (Tabular Only)

# COMMAND ----------

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    roc_auc_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix, roc_curve,
    ConfusionMatrixDisplay,
)

def train_and_log(model_name, feature_cols, X_train, X_test, y_train, y_test):
    """Train a GBM, log to MLflow, return model and metrics."""

    with mlflow.start_run(run_name=model_name):
        clf = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            random_state=42,
        )
        clf.fit(X_train[feature_cols], y_train)
        y_pred = clf.predict(X_test[feature_cols])
        y_prob = clf.predict_proba(X_test[feature_cols])[:, 1]

        metrics = {
            "auc":       roc_auc_score(y_test, y_prob),
            "precision": precision_score(y_test, y_pred),
            "recall":    recall_score(y_test, y_pred),
            "f1":        f1_score(y_test, y_pred),
        }

        mlflow.log_param("model_type", "GradientBoosting")
        mlflow.log_param("features", model_name)
        mlflow.log_param("n_features", len(feature_cols))
        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(clf, artifact_path="model")

        print(f"\n{'='*60}")
        print(f"  {model_name}")
        print(f"{'='*60}")
        for k, v in metrics.items():
            print(f"  {k:>12s}: {v:.4f}")

        return clf, metrics

# COMMAND ----------

baseline_clf, baseline_metrics = train_and_log(
    "Baseline (Tabular Only)",
    TABULAR_FEATURES,
    X_train, X_test, y_train, y_test,
)

# COMMAND ----------

# MAGIC %md ## 8. Train Graph-Augmented Model

# COMMAND ----------

graph_clf, graph_metrics = train_and_log(
    "Graph-Augmented (Tabular + Neo4j GDS)",
    ALL_FEATURES,
    X_train, X_test, y_train, y_test,
)

# COMMAND ----------

# MAGIC %md ---
# MAGIC ## 9. Head-to-Head Comparison

# COMMAND ----------

comparison = pd.DataFrame({
    "Metric":          ["AUC", "Precision", "Recall", "F1"],
    "Baseline":        [baseline_metrics["auc"], baseline_metrics["precision"],
                        baseline_metrics["recall"], baseline_metrics["f1"]],
    "Graph-Augmented": [graph_metrics["auc"], graph_metrics["precision"],
                        graph_metrics["recall"], graph_metrics["f1"]],
})
comparison["Lift"] = comparison["Graph-Augmented"] - comparison["Baseline"]
comparison["Lift %"] = (comparison["Lift"] / comparison["Baseline"] * 100).round(1)

display(spark.createDataFrame(comparison))

# COMMAND ----------

# MAGIC %md ## 10. Feature Importance — What Drives the Graph-Augmented Model?

# COMMAND ----------

importances = pd.DataFrame({
    "feature":    ALL_FEATURES,
    "importance": graph_clf.feature_importances_,
}).sort_values("importance", ascending=False)

display(spark.createDataFrame(importances.head(15)))

# COMMAND ----------

# MAGIC %md ## 11. ROC Curve Comparison

# COMMAND ----------

import matplotlib.pyplot as plt

y_prob_baseline = baseline_clf.predict_proba(X_test[TABULAR_FEATURES])[:, 1]
y_prob_graph    = graph_clf.predict_proba(X_test[ALL_FEATURES])[:, 1]

fpr_b, tpr_b, _ = roc_curve(y_test, y_prob_baseline)
fpr_g, tpr_g, _ = roc_curve(y_test, y_prob_graph)

fig, ax = plt.subplots(figsize=(8, 6))
ax.plot(fpr_b, tpr_b, label=f"Baseline (AUC={baseline_metrics['auc']:.3f})", linewidth=2)
ax.plot(fpr_g, tpr_g, label=f"Graph-Augmented (AUC={graph_metrics['auc']:.3f})", linewidth=2)
ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
ax.set_xlabel("False Positive Rate")
ax.set_ylabel("True Positive Rate")
ax.set_title("ROC Curve — Baseline vs Graph-Augmented")
ax.legend(loc="lower right")
plt.tight_layout()
display(fig)

# COMMAND ----------

# MAGIC %md ## 12. Confusion Matrix Deep-Dive

# COMMAND ----------

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

y_pred_baseline = baseline_clf.predict(X_test[TABULAR_FEATURES])
y_pred_graph    = graph_clf.predict(X_test[ALL_FEATURES])

ConfusionMatrixDisplay.from_predictions(y_test, y_pred_baseline, ax=axes[0], cmap="Blues")
axes[0].set_title(f"Baseline (AUC={baseline_metrics['auc']:.3f})")

ConfusionMatrixDisplay.from_predictions(y_test, y_pred_graph, ax=axes[1], cmap="Oranges")
axes[1].set_title(f"Graph-Augmented (AUC={graph_metrics['auc']:.3f})")

plt.tight_layout()
display(fig)

# COMMAND ----------

# MAGIC %md ---
# MAGIC ## 13. The Money Slide
# MAGIC
# MAGIC Translate model lift into estimated business impact.

# COMMAND ----------

avg_fraud_loss     = 5000  # dollars per undetected fraud case
test_fraud_count   = y_test.sum()

baseline_caught    = (y_pred_baseline[y_test == 1] == 1).sum()
graph_caught       = (y_pred_graph[y_test == 1] == 1).sum()
additional_caught  = graph_caught - baseline_caught

print(f"Fraud cases in test set:        {test_fraud_count}")
print(f"Baseline caught:                {baseline_caught}  ({baseline_caught/test_fraud_count*100:.1f}%)")
print(f"Graph-augmented caught:         {graph_caught}  ({graph_caught/test_fraud_count*100:.1f}%)")
print(f"Additional fraud caught:        {additional_caught}")
print(f"Est. savings (@ ${avg_fraud_loss:,}/case): ${additional_caught * avg_fraud_loss:,.0f}")

# COMMAND ----------

# MAGIC %md ---
# MAGIC ## Key Takeaway
# MAGIC
# MAGIC > Three graph algorithms from Neo4j GDS — computed in seconds in Aura —
# MAGIC > gave us more predictive lift than months of manual tabular feature engineering.
# MAGIC
# MAGIC The graph features capture **structural signals** (centrality, clustering,
# MAGIC shared counterparties) that simply don't exist in flat transaction tables.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Demo Flow Recap
# MAGIC
# MAGIC | Step | Notebook | Where |
# MAGIC |------|----------|-------|
# MAGIC | 1. Generate synthetic fraud data | `00_setup_and_data` | Databricks |
# MAGIC | 2. Push to Neo4j Aura | `01_neo4j_ingest` | Databricks |
# MAGIC | 3. Run GDS algorithms | `02_aura_gds_guide` | Neo4j Aura Workspace |
# MAGIC | 4. Pull features & train models | **`03_pull_and_model`** | Databricks |
# MAGIC
# MAGIC ### The Bidirectional Loop
# MAGIC ```
# MAGIC Delta Lake ──► Neo4j Aura ──► GDS (PageRank, Louvain, Similarity)
# MAGIC                                          │
# MAGIC Feature Store ◄── Training Table ◄── Spark Connector Read
# MAGIC      │
# MAGIC   ML Model  (baseline vs graph-augmented)
# MAGIC ```
