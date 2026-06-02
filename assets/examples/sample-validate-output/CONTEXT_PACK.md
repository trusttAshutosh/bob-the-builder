# Bob context pack

Ticket: `sample-gateway-health-check`
Generated: 2026-06-03 02:11:03

## Your Bob preferences (from user.env)

- **BOB_HOME:** `C:\Users\ashutosh.kumar\Desktop\novopay\bob-the-builder\assets`
- **BOB_LOCAL:** `C:\Users\ashutosh.kumar\Desktop\novopay\bob-the-builder\local`
- **BOB_THE_BUILDER_BASE:** `http://localhost:8080`
- **BUILDER_WORKSPACE_ROOT:** `C:\Users\ashutosh.kumar\Desktop\novopay`
- **CC_BASE:** `http://localhost:8016/cc-mgmt`
- **LOGS_DIR:** `C:\Users\ashutosh.kumar\Desktop\novopay\SERVER_LOGS`
- **MD_BASE:** `http://localhost:8015/masterdata`
- **MYSQL_HOST:** `127.0.0.1`
- **MYSQL_PORT:** `3306`
- **MYSQL_USER:** `root`

## Staleness checks

- **WARN** `spec_newer_than_graph`: ticket-spec.yaml is newer than platform-graph.yaml.
  - Fix: `bob sync-graph`
- **WARN** `catalog_empty`: API catalog is empty but ticket lists gateway_apis.
  - Fix: `bob discover-apis`

## Postman defaults (ticket-spec)

- local gateway: `http://localhost:8080/api-gateway`
- QA gateway: ``

## Hybrid retrieval (ranked)

# Context slice (hybrid retrieval)

**Query terms:** sample, gateway, health, check, and, audit, proof, inquirecardeligibility, inquirecardeligibilityprocessor
**Platform graph:** novopay-platform-creditcard-management updated 2026-05-25T10:26:02
**Hits:** 54 (lexical rank + API→processor expansion)

## Api (20)

- **inquireCardEligibility** (score 2.45) — path=/api/v1/inquireCardEligibility beans=2
- **uploadBkycFile** (score 2.00) — path=/api/v1/uploadBkycFile beans=5
- **uploadDvkycFile** (score 2.00) — path=/api/v1/uploadDvkycFile beans=5
- **uploadLeadReassignFile** (score 2.00) — path=/api/v1/uploadLeadReassignFile beans=5
- **manageLOCTransactionAudit** (score 1.51) — path=/api/v1/manageLOCTransactionAudit beans=3
- **checkPerfiosTxnStatus** (score 1.51) — path=/api/v1/checkPerfiosTxnStatus beans=3
- **getCCTransactionAttributes** (score 1.41) — path=/api/v1/getCCTransactionAttributes beans=4
- **validateField** (score 1.41) — path=/api/v1/validateField beans=4
- **dvkycRetrigger** (score 1.33) — path=/api/v1/dvkycRetrigger beans=5
- **fetchCustomerDetailsWithDedupe** (score 1.33) — path=/api/v1/fetchCustomerDetailsWithDedupe beans=5
- **fetchEkycDetailsForCC** (score 1.33) — path=/api/v1/fetchEkycDetailsForCC beans=5
- **fetchEkycDetailsForCCDSA** (score 1.33) — path=/api/v1/fetchEkycDetailsForCCDSA beans=5

## Processor (34)

- **inquireCardEligibilityProcessor** (score 2.08) <- inquireCardEligibility — in.novopay.creditcard.loc.processors.InquireCardEligibilityProcessor
- **uniqueFileNameCheckProcessor** (score 1.70) <- uploadBkycFile — in.novopay.creditcard.common.processors.UniqueFileNameCheckProcessor
- **uploadBkycFileProcessor** (score 1.70) <- uploadBkycFile — in.novopay.creditcard.transaction.processor.UploadBkycFileProcessor
- **uniqueFileNameCheckForDvkycProcessor** (score 1.70) <- uploadDvkycFile — in.novopay.creditcard.common.processors.UniqueFileNameCheckForDvkycProcessor
- **uploadDvkycFileProcessor** (score 1.70) <- uploadDvkycFile — in.novopay.creditcard.transaction.processor.UploadDvkycFileProcessor
- **uniqueFileNameCheckForLeadReassignProcessor** (score 1.70) <- uploadLeadReassignFile — in.novopay.creditcard.common.processors.UniqueFileNameCheckForLeadReassignProcessor
- **uploadLeadReassignFileProcessor** (score 1.70) <- uploadLeadReassignFile — in.novopay.creditcard.common.processors.UploadLeadReassignFileProcessor
- **leadReassignAuditProcessor** (score 1.70) <- uploadLeadReassignFile — in.novopay.creditcard.common.processors.LeadReassignAuditProcessor
- **fetchAgentDetailsProcessor** (score 1.29) <- manageLOCTransactionAudit — in.novopay.creditcard.common.processors.FetchAgentDetailsProcessor
- **manageLOCTransactionAuditProcessor** (score 1.29) <- manageLOCTransactionAudit — in.novopay.creditcard.common.processors.ManageLOCTransactionAuditProcessor
- **checkPerfiosTxnStatusProcessor** (score 1.29) <- checkPerfiosTxnStatus — in.novopay.creditcard.transaction.processor.CheckPerfiosTxnStatusProcessor
- **getTransactionAuditProcessor** (score 1.20) <- getCCTransactionAttributes — in.novopay.creditcard.common.processors.GetTransactionAuditProcessor
