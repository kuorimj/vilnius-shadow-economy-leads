CREATE TABLE IF NOT EXISTS staging.companies (
    snapshot_month  month_start  NOT NULL,
    company_code    text         NOT NULL,
    name            text         NOT NULL,
    legal_form      text,
    address         text,
    registered_on   date,
    status          text,
    activity_code   text,
    activity_name   text,
    PRIMARY KEY (snapshot_month, company_code)
);

CREATE TABLE IF NOT EXISTS staging.company_monthly (
    snapshot_month  month_start     NOT NULL,
    company_code    text            NOT NULL,
    month           month_start     NOT NULL,
    insured         integer,
    avg_wage        numeric(10, 2),
    contributions   numeric(14, 2),
    PRIMARY KEY (snapshot_month, company_code, month)
);