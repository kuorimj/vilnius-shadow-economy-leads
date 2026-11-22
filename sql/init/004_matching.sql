CREATE TABLE IF NOT EXISTS staging.place_matches (
    snapshot_month   text         NOT NULL,
    cid              text         NOT NULL,
    match_status     text         NOT NULL CHECK (match_status IN ('confirmed', 'possible', 'ambiguous', 'unmatched')),
    company_code     text,
    name_similarity  numeric(3, 2),
    activity_fits    boolean,
    same_address     boolean,
    candidates       integer      NOT NULL,
    PRIMARY KEY (snapshot_month, cid)
);