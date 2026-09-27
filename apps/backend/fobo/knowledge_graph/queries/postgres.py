"""Dialect-specific SQL.

An Oracle variant lands beside this file and is selected by a dialect
setting, without touching repository callers.
"""

from sqlalchemy import text

LINEAGE_CTE = text("""
WITH RECURSIVE lineage(node_id, depth) AS (
    SELECT e.to_node_id, 0
    FROM edge e
    WHERE e.from_node_id = :book_id
      AND e.edge_type = :edge_type
      AND e.valid_from <= :as_of
      AND (e.valid_to IS NULL OR e.valid_to >= :as_of)
    UNION ALL
    SELECT e.to_node_id, l.depth + 1
    FROM edge e
    JOIN lineage l ON e.from_node_id = l.node_id
    WHERE l.depth < :max_depth
      AND e.valid_from <= :as_of
      AND (e.valid_to IS NULL OR e.valid_to >= :as_of)
)
SELECT node_id, depth FROM lineage
""")
