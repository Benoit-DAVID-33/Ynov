

WITH agg AS (
    SELECT
        simulation_id,
        MAX(turn)                            AS total_turns,
        SUM(gold_collected::INT)             AS gold_collected,
        MAX(initial_gold_count)              AS initial_gold,
        SUM(was_blocked::INT)                AS blocked_turns,
        SUM(decision_correct::INT)           AS correct_decisions,
        COUNT(*)                             AS total_decisions,
        ROUND(AVG(nearest_gold_distance), 4) AS avg_nearest_gold_dist
    FROM "npc_brain"."main"."silver"
    GROUP BY simulation_id
),

kpis AS (
    SELECT *,
        ROUND(gold_collected  * 1.0 / NULLIF(initial_gold,     0), 4) AS gold_collection_rate,
        ROUND(correct_decisions * 1.0 / NULLIF(total_decisions, 0), 4) AS decision_accuracy
    FROM agg
)

SELECT *,
    ROUND(
        gold_collection_rate * 0.6
        + decision_accuracy  * 0.3
        + (1.0 - blocked_turns * 1.0 / NULLIF(total_turns, 0)) * 0.1
    , 3) AS efficiency_score,

    CASE
        WHEN gold_collection_rate = 1.0  THEN 'Victoire complète'
        WHEN gold_collection_rate >= 0.5 THEN 'Victoire partielle'
        WHEN gold_collected > 0          THEN 'Progrès minimal'
        ELSE 'Échec'
    END AS simulation_type

FROM kpis