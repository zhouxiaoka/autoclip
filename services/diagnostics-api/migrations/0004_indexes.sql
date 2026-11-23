-- Secondary and partial indexes to eliminate full table scans on objects and
-- historical deleted cases during hot-path commits and hourly sweep().

CREATE INDEX IF NOT EXISTS idx_objects_case_id_state
  ON objects (case_id, state);

CREATE INDEX IF NOT EXISTS idx_cases_active
  ON cases (state, case_id, landed_bytes, reserved_bytes)
  WHERE state != 'deleted';

CREATE INDEX IF NOT EXISTS idx_objects_live
  ON objects (case_id, r2_key, state)
  WHERE state != 'aborted';
