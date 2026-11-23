-- Every confirmed company that was scored, flagged or not: the population behind the lead list.
CREATE TABLE IF NOT EXISTS mart.company_scores (
    snapshot_month         month_start    NOT NULL,
    company_code           text           NOT NULL,
    company_name           text           NOT NULL,
    category               text           NOT NULL,
    places                 integer        NOT NULL,
    reviews                integer        NOT NULL,
    insured                integer        NOT NULL,
    typical_insured        numeric(6, 1)  NOT NULL,
    reviews_per_employee   numeric(10, 1) NOT NULL,
    times_category_median  numeric(10, 1) NOT NULL,
    revenue                numeric(14, 0),
    revenue_year           integer,
    revenue_dropped        boolean        NOT NULL,
    below_wages            boolean        NOT NULL,
    lead_type              text           CHECK (lead_type IN ('staff', 'sales')),
    PRIMARY KEY (snapshot_month, company_code)
);

-- One row per lead and place: the Google listing, why it was matched, and the official records behind the lead.
CREATE OR REPLACE VIEW mart.lead_evidence AS
SELECT l.snapshot_month,
       l.rank,
       l.lead_type,
       l.company_code,
       l.company_name,
       p.cid,
       'https://www.google.com/maps?cid=' || p.cid  AS google_maps,
       p.name                                     AS place_name,
       p.address                                  AS place_address,
       p.google_category,
       p.rating,
       p.reviews_count,
       p.areas                                    AS found_in_neighbourhoods,
       g.source_pages,
       g.fetched_at,
       m.name_similarity,
       m.activity_fits,
       m.same_address,
       m.candidates,
       c.address                                  AS registered_address,
       c.registered_on,
       c.status,
       c.activity_code,
       c.activity_name,
       s.month                                    AS sodra_month,
       s.insured,
       s.avg_wage,
       r.period_end                               AS revenue_period_end,
       r.revenue
FROM mart.leads l
JOIN staging.place_matches m
  ON m.snapshot_month = l.snapshot_month AND m.company_code = l.company_code AND m.match_status = 'confirmed'
JOIN staging.google_places p
  ON p.snapshot_month = m.snapshot_month AND p.cid = m.cid
JOIN staging.companies c
  ON c.snapshot_month = l.snapshot_month AND c.company_code = l.company_code
LEFT JOIN staging.company_monthly s
  ON s.snapshot_month = l.snapshot_month AND s.company_code = l.company_code AND s.month = l.sodra_month
LEFT JOIN LATERAL (
    SELECT array_agg(DISTINCT source_file ORDER BY source_file) AS source_pages, max(fetched_at) AS fetched_at
    FROM raw.google_listings
    WHERE snapshot_month = p.snapshot_month AND cid = p.cid
) g ON true
LEFT JOIN LATERAL (
    SELECT period_end, revenue
    FROM staging.company_revenue
    WHERE snapshot_month = l.snapshot_month AND company_code = l.company_code
    ORDER BY period_end DESC, submitted_on DESC
    LIMIT 1
) r ON true;

-- Per month and category: how many places were found, matched and assessed, and what share was flagged.
CREATE OR REPLACE VIEW mart.category_summary AS
WITH places AS (
    SELECT p.snapshot_month,
           t.category,
           count(*)                                           AS places,
           count(*) FILTER (WHERE m.match_status = 'confirmed') AS confirmed_places
    FROM staging.google_places p
    CROSS JOIN LATERAL unnest(p.categories) AS t(category)
    JOIN staging.place_matches m ON m.snapshot_month = p.snapshot_month AND m.cid = p.cid
    GROUP BY p.snapshot_month, t.category
),
companies AS (
    SELECT snapshot_month,
           category,
           count(*)                                   AS assessed_companies,
           count(lead_type)                           AS leads,
           count(*) FILTER (WHERE lead_type = 'staff') AS staff_leads,
           count(*) FILTER (WHERE lead_type = 'sales') AS sales_leads
    FROM mart.company_scores
    GROUP BY snapshot_month, category
)
SELECT p.snapshot_month,
       p.category,
       p.places,
       p.confirmed_places,
       c.assessed_companies,
       c.leads,
       c.staff_leads,
       c.sales_leads,
       round(c.leads::numeric / nullif(c.assessed_companies, 0), 3) AS share_flagged
FROM places p
LEFT JOIN companies c USING (snapshot_month, category);

-- Each assessed company's lead status compared with its previous assessed month.
CREATE OR REPLACE VIEW mart.lead_changes AS
SELECT snapshot_month,
       company_code,
       company_name,
       category,
       lead_type,
       lag(snapshot_month) OVER w AS previous_month,
       lag(lead_type) OVER w      AS previous_lead_type,
       CASE
           WHEN lead_type IS NOT NULL AND lag(lead_type) OVER w IS NULL THEN 'new'
           WHEN lead_type IS NOT NULL THEN 'repeat'
           WHEN lag(lead_type) OVER w IS NOT NULL THEN 'dropped'
       END                        AS change
FROM mart.company_scores
WINDOW w AS (PARTITION BY company_code ORDER BY snapshot_month);
