CREATE TABLE IF NOT EXISTS staging.company_revenue (
    snapshot_month  month_start     NOT NULL,
    company_code    text            NOT NULL,
    period_start    date            NOT NULL,
    period_end      date            NOT NULL,
    submitted_on    date            NOT NULL,
    revenue         numeric(14, 2),
    PRIMARY KEY (snapshot_month, company_code, period_start, period_end, submitted_on)
);
