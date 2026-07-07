{{ config(materialized='table') }}

WITH base AS (
    SELECT * FROM read_parquet('data/bronze.parquet')
),

enriched AS (
    SELECT
        *,
        COALESCE(nearest_gold_direction, 'AUCUN') AS nearest_gold_direction_clean,
        COALESCE(nearest_gold_distance,  0.0)      AS nearest_gold_distance_clean,

        CASE
            WHEN golds_count = 0 OR decision IS NULL THEN FALSE
            WHEN decision = 'HAUT'   AND nearest_gold_direction IN ('NORD', 'NORD-EST', 'NORD-OUEST')   THEN TRUE
            WHEN decision = 'BAS'    AND nearest_gold_direction IN ('SUD',  'SUD-EST',  'SUD-OUEST')    THEN TRUE
            WHEN decision = 'GAUCHE' AND nearest_gold_direction IN ('OUEST', 'NORD-OUEST', 'SUD-OUEST') THEN TRUE
            WHEN decision = 'DROITE' AND nearest_gold_direction IN ('EST',   'NORD-EST',   'SUD-EST')   THEN TRUE
            ELSE FALSE
        END AS decision_correct,

        SUM(gold_collected::INT) OVER (
            PARTITION BY simulation_id ORDER BY turn
        ) AS gold_collected_cumsum,

        ((turn - 1) / 5) * 5 + 1 AS turn_block,

        ABS(player_row - LAG(player_row, 1, player_row) OVER (PARTITION BY simulation_id ORDER BY turn))
        + ABS(player_col - LAG(player_col, 1, player_col) OVER (PARTITION BY simulation_id ORDER BY turn))
            AS manhattan_move

    FROM base
)

SELECT
    simulation_id, model, turn, player_row, player_col,
    golds_count, ennemies_count,
    nearest_gold_direction_clean AS nearest_gold_direction,
    nearest_gold_distance_clean  AS nearest_gold_distance,
    blocked_directions,
    decision, moved, was_blocked, gold_collected,
    gold_remaining, initial_gold_count,
    decision_correct, gold_collected_cumsum, turn_block, manhattan_move
FROM enriched
