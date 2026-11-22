CREATE TABLE IF NOT EXISTS mart.leads (
    snapshot_month        text           NOT NULL,
    rank                  integer        NOT NULL,
    company_code          text           NOT NULL,
    company_name          text           NOT NULL,
    legal_form            text,
    category              text           NOT NULL,
    places                text           NOT NULL,
    reviews               integer        NOT NULL,
    insured               integer        NOT NULL,
    typical_insured       numeric(6, 1)  NOT NULL,
    reviews_per_employee  numeric(10, 1) NOT NULL,
    times_category_median numeric(10, 1) NOT NULL,
    sodra_month           date           NOT NULL,
    supporting_reasons    text[]         NOT NULL,
    caveats               text[]         NOT NULL,
    explanation           text           NOT NULL,
    PRIMARY KEY (snapshot_month, company_code)
);