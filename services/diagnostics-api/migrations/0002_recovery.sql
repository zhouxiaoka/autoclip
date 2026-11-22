-- Recovery keys authenticate cancellation even when the create response was lost.
ALTER TABLE cases ADD COLUMN recovery_sha256 TEXT NOT NULL DEFAULT '';
CREATE TABLE creation_cancellations (
  idempotency_key TEXT NOT NULL,
  recovery_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (idempotency_key, recovery_sha256)
);
-- Cancellation tombstones deliberately outlive the upload: a delayed create must
-- never recreate data after cancellation. They contain hashes only, not media.

-- Repair counters from durable object transitions if an older Worker stopped
-- between its separate writes. Keep object identities/capabilities and failed cases.
UPDATE cases SET
  reserved_bytes = (SELECT COALESCE(SUM(declared_bytes), 0) FROM objects WHERE objects.case_id = cases.case_id AND objects.state = 'reserved'),
  landed_bytes = manifest_bytes + (SELECT COALESCE(SUM(declared_bytes), 0) FROM objects WHERE objects.case_id = cases.case_id AND objects.state = 'complete'),
  state = CASE
    WHEN state = 'failed' OR EXISTS (SELECT 1 FROM objects WHERE objects.case_id = cases.case_id AND objects.state = 'aborted') THEN 'failed'
    WHEN EXISTS (SELECT 1 FROM objects WHERE objects.case_id = cases.case_id AND objects.state = 'reserved') THEN 'open'
    ELSE 'complete' END
WHERE state IN ('open', 'complete', 'failed');
UPDATE quota SET
  landed_bytes = (SELECT COALESCE(SUM(landed_bytes), 0) FROM cases WHERE state != 'deleted'),
  reserved_bytes = (SELECT COALESCE(SUM(reserved_bytes), 0) FROM cases WHERE state != 'deleted')
WHERE id = 1;
