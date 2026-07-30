#!/usr/bin/env bash
# End-to-end smoke for the W5 clinical endpoints against the LOCAL Supabase stack
# (`npx supabase start`) — the path the dashboard takes once the *_VIA_BACKEND
# flags are on. Unlike supabase/tests/*.sql this drives real HTTP with a real
# GoTrue token, so it covers the router wiring, the role gates and the tenant
# resolution that SQL assertions cannot see.
#
# Prerequisites:
#   npx supabase start
#   PYTHONPATH=src SUPABASE_URL=http://127.0.0.1:54321 \
#     DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres \
#     BACKEND_API_KEY=staging-local-api-key CHECKPOINTER_BACKEND=memory \
#     poetry run uvicorn clinicai.main:app --port 8100
#   a staff login (see the fixture section for the account it expects)
set -uo pipefail
REPO=/Users/quangdang/Projects/Dr4Women-MacMini
API=http://127.0.0.1:8100
SUPA=http://127.0.0.1:54321
DB="postgresql://postgres:postgres@127.0.0.1:54322/postgres"
KEY=staging-local-api-key
pass=0; fail=0

eval "$(cd "$REPO" && npx --yes supabase@latest status -o env 2>/dev/null)"

login() { # email password -> access token
  curl -s -X POST "$SUPA/auth/v1/token?grant_type=password" -H "apikey: $ANON_KEY" \
    -H "Content-Type: application/json" -d "{\"email\":\"$1\",\"password\":\"$2\"}" \
    | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))'
}

call() { # method path token body -> "HTTP <code> <body>"
  local m=$1 p=$2 t=$3 b=${4:-}
  local args=(-s -o /tmp/e2e.out -w '%{http_code}' -X "$m" "$API$p"
              -H "Authorization: Bearer $t" -H "X-API-Key: $KEY"
              -H "Idempotency-Key: $(uuidgen)")
  [ -n "$b" ] && args+=(-H "Content-Type: application/json" -d "$b")
  echo "$(curl "${args[@]}") $(head -c 220 /tmp/e2e.out)"
}

check() { # label expected_code actual_line
  local code=${3%% *}
  if [ "$code" = "$2" ]; then printf '  PASS  %-56s %s\n' "$1" "$code"; pass=$((pass+1))
  else printf '  FAIL  %-56s got %s\n        %s\n' "$1" "$code" "${3#* }"; fail=$((fail+1)); fi
}

# appointment, visit and lab_result are append-only (prevent_hard_delete), and a
# FINALIZED visit cannot be moved back (visit_finalized_block_update, TT13). So
# the fixture builds a NEW appointment every run instead of trying to reset one.
APPT=$(uuidgen | tr 'A-Z' 'a-z')
PATIENT=e0000000-0000-4000-8000-0000000000f1
echo "=== fixtures (appointment $APPT) ==="
# One offset for both ends, or slot_end lands before slot_start.
OFFSET_MIN=$(( (RANDOM % 20000 + 1) * 20 ))
psql "$DB" -q -v appt="$APPT" -v mins="$OFFSET_MIN" <<'SQL'
INSERT INTO appointment (id, clinic_id, clinic_patient_id, location_id,
                         service_type_id, slot_start, slot_end, status, doctor_id)
SELECT :'appt'::uuid, 'a0000000-0000-4000-8000-000000000001',
       'e0000000-0000-4000-8000-0000000000f1',
       (SELECT id FROM clinic_location WHERE clinic_id='a0000000-0000-4000-8000-000000000001' LIMIT 1),
       -- Each run needs its own 15-minute window: enforce_slot_capacity allows
       -- 2+1 bookings per doctor per window (CAP-01), so reusing now() makes the
       -- third run fail on a rule that is doing its job.
       (SELECT id FROM service_type LIMIT 1),
       now() + (:mins * interval '1 minute'),
       now() + (:mins * interval '1 minute') + interval '30 minutes',
       'CHECKED_IN',
       (SELECT id FROM staff WHERE full_name='BS A local');
SQL
psql "$DB" -tAc "SELECT '  doctor on the appointment: ' || (SELECT full_name FROM staff WHERE id=doctor_id) FROM appointment WHERE id='$APPT';"

TOKEN=$(login bs.a@dr4women.local clinic-test-pw-123)
[ -z "$TOKEN" ] && { echo "could not sign in"; exit 1; }
echo "signed in as BS A local (DOCTOR)"

echo
echo "=== lab: order + enter result ==="
r=$(call POST /api/v1/lab/orders "$TOKEN" '{"clinic_patient_id":"'"$PATIENT"'","test_name":"E2E test"}')
check "doctor orders a test" 201 "$r"
LAB=$(python3 -c 'import json;print(json.load(open("/tmp/e2e.out")).get("lab_result_id",""))' 2>/dev/null)
r=$(call PATCH "/api/v1/lab/results/$LAB" "$TOKEN" '{"result_link":"drive.google.com/file/xyz"}')
check "result attaches, link gets a scheme" 200 "$r"
psql "$DB" -tAc "SELECT '        stored external_ref = ' || external_ref FROM lab_result WHERE lab_result_id='$LAB';"
r=$(call PATCH "/api/v1/lab/results/$LAB" "$TOKEN" '{}')
check "empty result update refused" 422 "$r"

echo
echo "=== clinical record: vitals then the doctor's save ==="
body=$(printf '{"appointment_id":"%s","clinic_patient_id":"%s","vitals_only":true,"objective":{"vitals":{"bp":"120/80","pulse":"78"}},"chief_complaint":"đau bụng"}' "$APPT" "$PATIENT")
r=$(call POST /api/v1/clinical-records "$TOKEN" "$body")
check "nurse-path vitals saved" 200 "$r"
body=$(printf '{"appointment_id":"%s","clinic_patient_id":"%s","objective":{"vitals":{"bp":""},"exam":"khám thường"},"assessment":{"dx":"X"},"prescriptions":[{"drug_name":"Paracetamol","quantity":"10","dosage":"1v x 2"}]}' "$APPT" "$PATIENT")
r=$(call POST /api/v1/clinical-records "$TOKEN" "$body")
check "doctor saves over it" 200 "$r"
psql "$DB" -tAc "SELECT '        vitals after doctor save = ' || (soap_objective->'vitals')::text FROM clinical_record cr JOIN visit v ON v.visit_id=cr.visit_id WHERE v.appointment_id='$APPT';"
psql "$DB" -tAc "SELECT '        prescriptions = ' || count(*) FROM prescription p JOIN visit v ON v.visit_id=p.visit_id WHERE v.appointment_id='$APPT';"

echo
echo "=== clinical form ==="
VISIT=$(psql "$DB" -tAc "SELECT visit_id FROM visit WHERE appointment_id='$APPT';" | tr -d ' ')
# A FORM code (PK/SK/NT/HMVS/NK), not a service_type code: service_code on
# clinical_form_response identifies the exam form, and the backend checks it
# against clinical_form_catalogue (migration 20260730000011).
CODE=$(psql "$DB" -tAc "SELECT form_code FROM clinical_form_catalogue WHERE is_active ORDER BY form_code LIMIT 1;" | tr -d ' ')
r=$(call PUT /api/v1/clinical-forms "$TOKEN" "{\"visit_id\":\"$VISIT\",\"service_code\":\"$CODE\",\"form_data\":{\"a\":1}}")
check "form saved for a known service code" 200 "$r"
r=$(call PUT /api/v1/clinical-forms "$TOKEN" "{\"visit_id\":\"$VISIT\",\"service_code\":\"NOPE\",\"form_data\":{}}")
check "unknown service code refused" 422 "$r"
psql "$DB" -q -c "UPDATE visit SET status='FINALIZED' WHERE visit_id='$VISIT';"
r=$(call PUT /api/v1/clinical-forms "$TOKEN" "{\"visit_id\":\"$VISIT\",\"service_code\":\"$CODE\",\"form_data\":{\"a\":2}}")
check "FINALIZED visit is read-only (ADR-0008)" 409 "$r"
# Deliberately NOT reset: visit_finalized_block_update refuses FINALIZED ->
# IN_PROGRESS, which is the TT13 guarantee. The next run gets a new appointment.

echo
echo "=== ultrasound: the role gate that must not widen ==="
body=$(printf '{"appointment_id":"%s","clinic_patient_id":"%s","measurements":{"bpd":45}}' "$APPT" "$PATIENT")
r=$(call POST /api/v1/ultrasound/measurements "$TOKEN" "$body")
check "a plain DOCTOR is refused (ULTRASOUND_DOCTOR only)" 403 "$r"

echo
echo "=== payment: the COMPLETED gate ==="
r=$(call POST /api/v1/payments "$TOKEN" "{\"visit_id\":\"$VISIT\",\"kind\":\"dich_vu\",\"amount\":150000}")
check "a doctor may not take money" 403 "$r"

echo
printf '=== %d passed, %d failed ===\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
