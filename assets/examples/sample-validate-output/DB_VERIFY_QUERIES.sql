-- Bob generated after validate-ticket. Your part: run these in MySQL Workbench.
-- @BASE_CRN: BOB-SAMPLE-20260601
-- Schema: dsa_credit_card_mgmt

SET @BASE_CRN = 'BOB-SAMPLE-20260601';

USE dsa_credit_card_mgmt;

-- Dashboard (all E2E scenarios): scenario_id, scenario_description, client_reference_code,
-- test_run_time, txn_status, txn_result_code, txn_result_description, internal_txn_desc, assert_result

SELECT * FROM (
SELECT 'S1' AS scenario_id, 'S1: Happy path — eligibility inquiry' AS scenario_description, 'BOB-SAMPLE-20260601-S1' AS client_reference_code, updated_on AS test_run_time, txn_status, txn_result_code, txn_result_description, internal_txn_desc, CASE WHEN COALESCE(txn_status, '') = 'SUCCESS' AND COALESCE(txn_result_code, '') = '000' THEN 'PASS' ELSE 'FAIL' END AS assert_result FROM transaction_audit WHERE client_reference_code='BOB-SAMPLE-20260601-S1' ORDER BY updated_on DESC LIMIT 1
) AS _bob_S1
UNION ALL
SELECT * FROM (
SELECT 'S2' AS scenario_id, 'S2: Integration — processor unit scope' AS scenario_description, 'BOB-SAMPLE-20260601-S2' AS client_reference_code, updated_on AS test_run_time, txn_status, txn_result_code, txn_result_description, internal_txn_desc, 'REVIEW' AS assert_result FROM transaction_audit WHERE client_reference_code='BOB-SAMPLE-20260601-S2' ORDER BY updated_on DESC LIMIT 1
) AS _bob_S2;

-- Per-scenario detail

-- S1: Happy path — eligibility inquiry
-- CRN: BOB-SAMPLE-20260601-S1
-- expect: {'txn_status': 'SUCCESS', 'txn_result_code': '000'}
SELECT 'S1' AS scenario_id, 'S1: Happy path — eligibility inquiry' AS scenario_description, 'BOB-SAMPLE-20260601-S1' AS client_reference_code, updated_on AS test_run_time, txn_status, txn_result_code, txn_result_description, internal_txn_desc, CASE WHEN COALESCE(txn_status, '') = 'SUCCESS' AND COALESCE(txn_result_code, '') = '000' THEN 'PASS' ELSE 'FAIL' END AS assert_result FROM transaction_audit WHERE client_reference_code='BOB-SAMPLE-20260601-S1' ORDER BY updated_on DESC LIMIT 1;

-- S2: Integration — processor unit scope
-- CRN: BOB-SAMPLE-20260601-S2
SELECT 'S2' AS scenario_id, 'S2: Integration — processor unit scope' AS scenario_description, 'BOB-SAMPLE-20260601-S2' AS client_reference_code, updated_on AS test_run_time, txn_status, txn_result_code, txn_result_description, internal_txn_desc, 'REVIEW' AS assert_result FROM transaction_audit WHERE client_reference_code='BOB-SAMPLE-20260601-S2' ORDER BY updated_on DESC LIMIT 1;
