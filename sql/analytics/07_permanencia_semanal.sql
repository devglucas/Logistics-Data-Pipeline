-- Permanência média por hub e semana: mostra quando cada gargalo aconteceu.
WITH sequencia AS (
    SELECT remessa_id, hub_id, codigo, ocorrido_em_utc, data_local,
           LEAD(ocorrido_em_utc) OVER viagem AS proximo_em,
           LEAD(hub_id) OVER viagem          AS proximo_hub
    FROM fato_evento
    WINDOW viagem AS (PARTITION BY remessa_id ORDER BY ocorrido_em_utc)
)
SELECT d.ano_semana, s.hub_id, COUNT(*) AS passagens,
       ROUND(AVG((julianday(s.proximo_em) - julianday(s.ocorrido_em_utc)) * 24), 1) AS horas_medias
FROM sequencia s
JOIN dim_data d ON d.data = s.data_local
WHERE s.codigo = 'RECEBIDO_HUB' AND s.proximo_hub = s.hub_id
GROUP BY d.ano_semana, s.hub_id
ORDER BY d.ano_semana, s.hub_id;
