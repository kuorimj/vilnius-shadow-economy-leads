-- Versions of each company and place across monthly snapshots (slowly changing dimension, type 2).
-- valid_from is the first month a version applied, valid_to the first month it no longer did.
CREATE TABLE IF NOT EXISTS mart.company_versions (
    company_code    text  NOT NULL,
    name            text  NOT NULL,
    legal_form      text,
    address         text,
    status          text,
    activity_code   text,
    valid_from      text  NOT NULL,
    valid_to        text,
    PRIMARY KEY (company_code, valid_from)
);

CREATE TABLE IF NOT EXISTS mart.place_versions (
    cid             text  NOT NULL,
    name            text  NOT NULL,
    address         text,
    google_category text,
    price_band      text,
    valid_from      text  NOT NULL,
    valid_to        text,
    PRIMARY KEY (cid, valid_from)
);

-- Month-to-month change in each place's reviews and rating.
CREATE OR REPLACE VIEW mart.place_review_changes AS
SELECT snapshot_month,
       cid,
       name,
       reviews_count,
       rating,
       lag(snapshot_month) OVER w                 AS previous_month,
       lag(reviews_count) OVER w                  AS previous_reviews,
       reviews_count - lag(reviews_count) OVER w  AS reviews_gained,
       rating - lag(rating) OVER w                AS rating_change
FROM staging.google_places
WINDOW w AS (PARTITION BY cid ORDER BY snapshot_month);

-- Month-to-month change in each company's insured employees, within each snapshot's Sodra data.
CREATE OR REPLACE VIEW mart.company_insured_changes AS
SELECT snapshot_month,
       company_code,
       month,
       insured,
       lag(insured) OVER w            AS previous_insured,
       insured - lag(insured) OVER w  AS insured_change
FROM staging.company_monthly
WINDOW w AS (PARTITION BY snapshot_month, company_code ORDER BY month);
