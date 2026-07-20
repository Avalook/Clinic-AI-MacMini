-- Hot-query indexes for the most frequently accessed tables.
-- Phase 4 of the System Design completion plan (Bài 18 — Indexing).
--
-- These cover the query patterns used by:
--   - Queue board (appointments by date + status)
--   - Booking overlap check (doctor + time range)
--   - Payment gate (visit → appointment lookup)

-- Queue: appointments by slot date, excluding dead statuses.
CREATE INDEX IF NOT EXISTS idx_appointment_slot_start_status
  ON appointment (slot_start, status)
  WHERE status NOT IN ('CANCELLED', 'NO_SHOW');

-- Booking: doctor overlap check (find conflicting slots for a doctor).
CREATE INDEX IF NOT EXISTS idx_appointment_doctor_slot
  ON appointment (doctor_id, slot_start, slot_end)
  WHERE status NOT IN ('CANCELLED', 'NO_SHOW');

-- Visit lookup by appointment (payment gate reads visit.appointment.status).
CREATE INDEX IF NOT EXISTS idx_visit_appointment_id
  ON visit (appointment_id)
  WHERE appointment_id IS NOT NULL;

-- Queue order: visits by date for queue_order.py call_rank.
CREATE INDEX IF NOT EXISTS idx_visit_created_at
  ON visit (created_at DESC);
