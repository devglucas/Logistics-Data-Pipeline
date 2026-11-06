-- Tempo parado em cada hub: do RECEBIDO_HUB até o evento seguinte da remessa (LEAD).
WITH sequencia AS (
    SELECT remessa_id, hub_id, codigo, ocorrido_em_utc,
           LEAD(ocorrido_em_utc) OVER viagem AS proximo_em,
           LEAD(hub_id) OVER viagem          AS proximo_hub
    FROM fato_evento
    WINDOW viagem AS (PARTITION BY remessa_id ORDER BY ocorrido_em_utc)
),
permanencia AS (
    SELECT hub_id, (julianday(proximo_em) - julianday(ocorrido_em_utc)) * 24 AS horas
    FROM sequencia
    WHERE codigo = 'RECEBIDO_HUB' AND proximo_hub = hub_id
)
SELECT p.hub_id, h.cidade, h.operador, COUNT(*) AS passagens,
       ROUND(AVG(p.horas), 1) AS horas_medias,
       ROUND(MAX(p.horas), 1) AS horas_maximas,
       RANK() OVER (ORDER BY AVG(p.horas) DESC) AS ranking_gargalo
FROM permanencia p
JOIN dim_hub h USING (hub_id)
GROUP BY p.hub_id
ORDER BY horas_medias DESC;
