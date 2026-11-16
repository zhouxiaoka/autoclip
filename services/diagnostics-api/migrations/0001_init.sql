-- Proposed schema for the uncreated D1 database autoclip-diagnostics-meta.
-- Quotas are application policy (approval pending), not a Cloudflare bill.

CREATE TABLE IF NOT EXISTS quota (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  landed_bytes INTEGER NOT NULL DEFAULT 0,
  reserved_bytes INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);

INSERT INTO quota (id, landed_bytes, reserved_bytes, updated_at)
VALUES (1, 0, 0, '1970-01-01T00:00:00Z')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS cases (
  case_id TEXT PRIMARY KEY,
  idempotency_key TEXT NOT NULL UNIQUE,
  manifest_sha256 TEXT NOT NULL,
  state TEXT NOT NULL,
  capability_sha256 TEXT NOT NULL,
  consent_version TEXT NOT NULL,
  manifest_bytes INTEGER NOT NULL,
  reserved_bytes INTEGER NOT NULL,
  landed_bytes INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS objects (
  object_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  role TEXT NOT NULL,
  r2_key TEXT NOT NULL,
  declared_bytes INTEGER NOT NULL,
  actual_bytes INTEGER,
  sha256 TEXT,
  upload_id TEXT,
  part_plan TEXT NOT NULL DEFAULT '[]',
  state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rate_windows (
  bucket TEXT NOT NULL,
  window_start TEXT NOT NULL,
  hits INTEGER NOT NULL,
  PRIMARY KEY (bucket, window_start)
);

-- Reservation is conditional. A client-supplied size cannot raise the cap.
-- landed + reserved + new <= landed cap AND reserved + new <= in-flight cap.
-- The Worker must use this predicate (see src/quota.ts) and check changes = 1.
