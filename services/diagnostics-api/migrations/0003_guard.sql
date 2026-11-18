-- A zero-row write does not fail a D1 batch, so it does not roll the batch back.
-- This row makes a broken accounting unit fail the statement and abort the batch.

CREATE TABLE IF NOT EXISTS write_guard (
  name TEXT PRIMARY KEY,
  ok INTEGER NOT NULL CHECK (ok = 1)
);
