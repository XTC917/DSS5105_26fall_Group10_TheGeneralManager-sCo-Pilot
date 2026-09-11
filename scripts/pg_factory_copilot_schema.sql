-- Local inspect copy of mid-platform app schema (no passwords).
-- Connect as postgres, database factory_copilot_db.

CREATE SCHEMA IF NOT EXISTS app AUTHORIZATION postgres;
CREATE SCHEMA IF NOT EXISTS admin_meta AUTHORIZATION postgres;

DROP TABLE IF EXISTS app.snapshot;
DROP TABLE IF EXISTS app.workshops;
DROP TABLE IF EXISTS app.production_log;
DROP TABLE IF EXISTS app.orders;
DROP TABLE IF EXISTS admin_meta.import_details;
DROP TABLE IF EXISTS admin_meta.upload_history;
DROP TABLE IF EXISTS admin_meta.data_sources;

CREATE TABLE app.orders (
  order_id text NOT NULL PRIMARY KEY,
  customer text NOT NULL,
  product text NOT NULL,
  category text NOT NULL CHECK (category IN ('TOPS', 'ACCESSORIES')),
  pieces integer NOT NULL CHECK (pieces > 0),
  order_date date NOT NULL,
  due_date date NOT NULL CHECK (due_date >= order_date),
  status text NOT NULL CHECK (status IN ('IN_PROGRESS', 'COMPLETE')),
  current_stage text NOT NULL CHECK (current_stage IN (
    'ORDERED', 'KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING', 'COMPLETE'
  )),
  last_activity_date date NOT NULL CHECK (last_activity_date >= order_date),
  completed_date date,
  days_late integer,
  CONSTRAINT orders_state_consistency CHECK (
    (
      status = 'IN_PROGRESS'
      AND current_stage IN ('ORDERED', 'KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING')
      AND completed_date IS NULL
      AND days_late IS NULL
    )
    OR (
      status = 'COMPLETE'
      AND current_stage = 'COMPLETE'
      AND completed_date IS NOT NULL
      AND completed_date = last_activity_date
      AND days_late IS NOT NULL
      AND days_late = completed_date - due_date
    )
  )
);

CREATE TABLE app.production_log (
  production_date date NOT NULL,
  stage text NOT NULL CHECK (stage IN ('KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING')),
  pieces_completed integer NOT NULL CHECK (pieces_completed >= 0),
  PRIMARY KEY (production_date, stage),
  CONSTRAINT pieces_completed_consistency CHECK (
    EXTRACT(ISODOW FROM production_date) <> 7 OR pieces_completed = 0
  )
);

CREATE TABLE app.workshops (
  workshop_id text NOT NULL,
  name text NOT NULL,
  capacity_pieces_per_day integer NOT NULL CHECK (capacity_pieces_per_day > 0),
  pickup_lead_days integer NOT NULL CHECK (pickup_lead_days >= 0),
  defect_rate numeric(5,4) NOT NULL CHECK (defect_rate >= 0 AND defect_rate <= 1),
  cost_per_piece numeric(10,2) NOT NULL CHECK (cost_per_piece >= 0),
  makes text NOT NULL CHECK (makes IN ('TOPS', 'ACCESSORIES')),
  status text NOT NULL CHECK (status IN ('ACTIVE', 'SUSPENDED')),
  max_batch_pieces integer CHECK (max_batch_pieces IS NULL OR max_batch_pieces > 0),
  current_queue_days numeric(6,2) NOT NULL CHECK (current_queue_days >= 0),
  notes text NOT NULL,
  PRIMARY KEY (workshop_id, makes),
  UNIQUE (name, makes)
);

CREATE TABLE app.snapshot (
  order_id text NOT NULL,
  status text NOT NULL CHECK (status IN ('IN_PROGRESS', 'COMPLETE')),
  stage text NOT NULL CHECK (stage IN (
    'ORDERED', 'KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING', 'COMPLETE'
  )),
  date date NOT NULL,
  CONSTRAINT snapshot_state_consistency CHECK (
    (
      status = 'IN_PROGRESS'
      AND stage IN ('ORDERED', 'KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING')
    )
    OR (status = 'COMPLETE' AND stage = 'COMPLETE')
  ),
  PRIMARY KEY (order_id, status, stage, date)
);

CREATE TABLE admin_meta.upload_history (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  file_name text NOT NULL,
  file_type text NOT NULL CHECK (file_type IN ('csv', 'excel')),
  total_rows integer NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'pending',
  error_message text,
  uploaded_by text NOT NULL DEFAULT 'admin',
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at timestamptz
);

CREATE TABLE admin_meta.import_details (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  upload_id bigint NOT NULL REFERENCES admin_meta.upload_history(id) ON DELETE CASCADE,
  file_name text NOT NULL,
  table_name text NOT NULL CHECK (table_name IN ('orders', 'production_log', 'workshops')),
  total_rows integer NOT NULL DEFAULT 0,
  success_rows integer NOT NULL DEFAULT 0,
  failed_rows integer NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'pending',
  error_message text,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at timestamptz
);

CREATE TABLE admin_meta.data_sources (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_name text NOT NULL,
  table_name text NOT NULL UNIQUE CHECK (table_name IN ('orders', 'production_log', 'workshops')),
  original_file text,
  description text,
  row_count integer NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO admin_meta.data_sources (source_name, table_name, original_file, row_count)
VALUES
  ('Orders', 'orders', 'orders.csv', 0),
  ('Production Log', 'production_log', 'production_log.csv', 0),
  ('Workshops', 'workshops', 'workshops.csv', 0);
