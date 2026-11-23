CREATE TABLE IF NOT EXISTS raw.google_listings (
    snapshot_month  month_start      NOT NULL,
    category        text             NOT NULL,
    area            text             NOT NULL,
    query           text             NOT NULL,
    fetched_at      timestamptz      NOT NULL,
    position        integer          NOT NULL,
    google_id       text             NOT NULL,
    cid             text,
    name            text             NOT NULL,
    rating          numeric(2, 1),
    reviews_count   integer,
    reviews_rounded boolean          NOT NULL,
    google_category text,
    address         text,
    price_band      text,
    years_in_business integer,
    lat             double precision,
    lng             double precision,
    source_file     text             NOT NULL,
    PRIMARY KEY (snapshot_month, category, area, position)
);

CREATE TABLE IF NOT EXISTS staging.google_places (
    snapshot_month  month_start      NOT NULL,
    cid             text             NOT NULL,
    google_id       text             NOT NULL,
    name            text             NOT NULL,
    rating          numeric(2, 1),
    reviews_count   integer,
    reviews_rounded boolean          NOT NULL,
    google_category text,
    address         text,
    price_band      text,
    years_in_business integer,
    lat             double precision NOT NULL,
    lng             double precision NOT NULL,
    appearances     integer          NOT NULL,
    categories      text[]           NOT NULL,
    areas           text[]           NOT NULL,
    best_position   integer          NOT NULL,
    PRIMARY KEY (snapshot_month, cid)
);

CREATE TABLE IF NOT EXISTS staging.google_coverage (
    snapshot_month  month_start NOT NULL,
    category        text        NOT NULL,
    area            text        NOT NULL,
    collected       boolean     NOT NULL,
    attempts        integer     NOT NULL,
    listings        integer     NOT NULL,
    fetched_at      timestamptz,
    PRIMARY KEY (snapshot_month, category, area)
);