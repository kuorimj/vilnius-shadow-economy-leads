CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- A month is stored as its first day, so it sorts, compares and does date arithmetic natively.
DO $$ BEGIN
    CREATE DOMAIN month_start AS date CHECK (extract(day FROM VALUE) = 1);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;