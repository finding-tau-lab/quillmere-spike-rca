-- Warehouse CLOB stand-in. SYNTHETIC. No vendor implied.
CREATE TABLE IF NOT EXISTS calls (
    call_id TEXT PRIMARY KEY,
    transcript_clob TEXT
);
