CREATE TABLE IF NOT EXISTS mart.quality_checks (
    snapshot_month  text         NOT NULL,
    check_name      text         NOT NULL,
    layer           text         NOT NULL,
    severity        text         NOT NULL CHECK (severity IN ('error', 'warn')),
    value           numeric,
    min_value       numeric,
    max_value       numeric,
    passed          boolean      NOT NULL,
    checked_at      timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (snapshot_month, check_name)
);
