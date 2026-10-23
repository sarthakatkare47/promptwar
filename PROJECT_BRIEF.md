# InvoiceGuard+ — Project Brief

> Part of the InvoiceGuard+ document set: **PROJECT_BRIEF** · [PRD](PRD.md) · [PLAN](PLAN.md) · [ARCHITECTURE](ARCHITECTURE.md) · [API_SPEC](API_SPEC.md) · [README](README.md)

| | |
|---|---|
| Status | Pre-implementation (documentation baseline) |
| Format | Three-hour solo hackathon |
| Label convention | **MVP** = built and demonstrated in the three hours · **Optional** = built only after every MVP item passes · **Future** = documented, not built, never described as implemented |

---

## 1. Executive summary

InvoiceGuard+ is a web application that helps Indian small businesses, accountants and finance teams screen purchase invoices before they are booked or paid. A user uploads an invoice (JPG, PNG or PDF). Google's Gemini API reads the document into a strict structured format. **Deterministic Python code, not the AI,** then checks GSTIN format and checksum, tax arithmetic, dates and duplicates, produces evidence-backed findings, and assigns a transparent risk level. A human reviews, corrects and approves, flags or rejects the invoice. Every action is recorded in an audit trail, and a **Trust Scorecard** reports measured accuracy, detection, latency, cost and security-test results from a reproducible synthetic test suite.

The central design principle: **the LLM extracts; code decides; a human approves.**

## 2. Problem statement

Small businesses re-type invoice details by hand and rarely cross-check them. Errors that follow:

- wrong or mistyped GSTINs (input tax credit can be disallowed),
- tax totals that do not add up,
- the same invoice entered or paid twice,
- unusual or unexpected documents that nobody looks at twice.

Manual checking is slow, inconsistent and undocumented.

## 3. Target users and use cases

| User | Use case |
|---|---|
| Shop or small-business owner | Check a supplier invoice before paying it |
| Accounts clerk / bookkeeper | Convert invoice images to clean rows and catch typing or tax mistakes |
| Accountant or CA firm staff | Triage a batch of client invoices; decide which need attention |
| Hackathon evaluator | Inspect the repository, run the tests and benchmark, and see the scorecard |

## 4. Current pain points

1. Data entry takes minutes per invoice and introduces typos.
2. GSTIN and tax errors are found late (at filing time) or not at all.
3. Duplicate invoices are caught only by memory.
4. There is no record of who decided what, and why.

## 5. Proposed solution

Upload → validate file → extract with Gemini → validate schema → run deterministic rules → score risk → human review → persist with audit trail → export. See the [workflow](#6-core-workflow) and [ARCHITECTURE](ARCHITECTURE.md).

## 6. Value proposition and differentiation

| Differentiator | What it means concretely |
|---|---|
| Hybrid design | Gemini only transcribes. All arithmetic, checksums, duplicate logic and risk scoring are deterministic and unit-tested. |
| Evidence-backed findings | Each finding has a stable rule ID, severity, plain-language explanation and the exact values compared. |
| Honest language | Findings are *review signals*, never "fraud detected". GSTIN checks never claim a registration is genuine. |
| Human in the loop | The system recommends; a person decides. Uncertain fields are highlighted for correction. |
| Verifiable claims | The Trust Scorecard is computed by a reproducible benchmark and shows sample size and limitations. |
| Safe failure | If Gemini fails, nothing is corrupted: the invoice is saved as `failed` and can be retried or entered manually. |

## 7. Core workflow

1. User uploads a JPG, PNG or PDF.
2. Backend checks size, allowlisted type and file signature, and (for PDFs and images) basic structural safety.
3. Gemini multimodal extraction returns structured JSON (schema-constrained, temperature 0, no tools).
4. Pydantic validates and normalises the output; malformed fields become `null` plus an uncertainty marker. Nothing is invented.
5. The rules engine checks GSTIN format/checksum, tax arithmetic (decimal), dates, duplicates and injection-like text.
6. The risk scorer sums rule severities into a level (`low` / `medium` / `high`) and a recommendation.
7. The reviewer corrects uncertain fields (findings are re-computed) and approves, flags, rejects or reopens.
8. Invoice, findings and audit events are stored in SQLite.
9. The reviewer exports CSV (invoices or findings).
10. The Trust Scorecard shows results from the last benchmark run.

## 8. MVP feature list

| ID | Feature | Label |
|---|---|---|
| F1 | Single-file upload with size / type / signature validation | MVP |
| F2 | Gemini structured extraction with schema validation | MVP |
| F3 | GSTIN format + checksum validation (offline) | MVP |
| F4 | Decimal tax arithmetic checks with documented tolerances | MVP |
| F5 | Date sanity checks | MVP |
| F6 | Duplicate detection (file-hash and business-key rules) | MVP |
| F7 | Prompt-injection text heuristic (review signal) | MVP |
| F8 | Transparent risk scoring with rule breakdown | MVP |
| F9 | Review UI with uncertain-field highlighting and corrections | MVP |
| F10 | Approve / flag / reject / reopen with audit trail | MVP |
| F11 | SQLite persistence | MVP |
| F12 | CSV export (invoices and findings) with formula-injection protection | MVP |
| F13 | Synthetic dataset generator, pytest suite, benchmark runner | MVP |
| F14 | Trust Scorecard (API + page) from measured results | MVP |
| F15 | Graceful Gemini failure: `failed` state, retry, manual entry | MVP |
| F16 | Batch upload (client-side queue), confidence-based routing, Gemini explanations, amount-anomaly rule, HTML report, read-only filter-based natural-language query | Optional |
| F17 | Firebase Auth, BigQuery, Cloud DLP, Cloud Storage, Cloud Run, Excel export, Hindi/Marathi, live GST registration verification | Future |

## 9. Explicitly out of scope

- Proving that an invoice, vendor or GST registration is genuine, or that fraud occurred.
- Live GSTIN status lookup (needs an authorised, available source; documented as Future).
- Credit notes, debit notes, e-invoice IRN/QR verification, GSTR reconciliation, bank-statement matching.
- Multi-user accounts, tenant isolation and production hardening (the MVP is a single-user local tool).
- Automatic approval or payment. A human always decides.
- Any unrestricted SQL or free-form LLM-generated SQL.

## 10. Assumptions and constraints

| # | Assumption / constraint |
|---|---|
| A1 | One developer, three hours, so SQLite and synchronous processing; no queue or microservices. |
| A2 | A Gemini API key is available. The default model name is configurable (`GEMINI_MODEL`); confirm the current model name and pricing before the event. |
| A3 | Test data is synthetic. Synthetic GSTINs are generated with the public checksum algorithm and are not real registrations. |
| A4 | Invoices are single-currency (INR assumed unless extracted otherwise) and are tax invoices, not credit notes. |
| A5 | The MVP runs locally, bound to `127.0.0.1`, with no authentication. This is a documented limitation, not a security feature. |
| A6 | Gemini data-handling terms depend on the API tier. Do not upload real confidential invoices with a free-tier key; verify the current terms. |
| A7 | GST slab rates change over time; rate plausibility is configurable and informational only. |

## 11. Success metrics

Measured, never asserted. Formulas are in [PRD §14](PRD.md#14-trust-scorecard).

| Metric | MVP target | How verified |
|---|---|---|
| End-to-end flow works (upload → review → export) | Demonstrable in ≤ 3 minutes | Demo script in [PLAN](PLAN.md) |
| Deterministic rules on labelled fixtures | 100 % of planted errors detected, 0 clean cases flagged (a miss is a bug in the rule or the fixture) | `pytest`, `python -m benchmark.run --mode deterministic` |
| Live extraction accuracy | **Reported, no pre-set target** | `python -m benchmark.run --mode live` |
| Prompt-injection containment | Reported against the fixed suite, with benign look-alikes | Benchmark |
| Deterministic scan latency | p95 < 50 ms per invoice | Benchmark |
| All P0 acceptance items checked | 100 % | [PRD §19 checklist](PRD.md#19-mvp-acceptance-checklist) |

## 12. Judging criteria and the evidence the repository will provide

| Criterion | What is implemented in the MVP | Evidence a reviewer can inspect |
|---|---|---|
| **1. Security** | Upload validation (size, allowlist, signature, image decode, PDF structure heuristics); no tools exposed to the model; schema-constrained output re-validated locally; injection heuristic; parameterised SQL only; CSV formula neutralisation; secrets server-side; log hygiene; review state machine; audit trail; optional bearer token; rate and daily AI-call limits. Documented limits: no auth or tenant isolation, no DLP. | `backend/app/services/upload_validation.py`, `backend/tests/security/`, [PRD §18](PRD.md#18-security-abuse-cases-and-mitigations), injection results on the scorecard |
| **2. Efficiency** | One Gemini call per invoice; deterministic rules cost no tokens; a hash match skips the AI call; token and cost tracking per call. | `ai_calls` table, scorecard cost metric, [ARCHITECTURE §14](ARCHITECTURE.md#14-performance-considerations) |
| **3. Technology Implemented** | Multimodal structured extraction, Pydantic validation, decimal rules engine, explainable scoring, state-machine review, benchmark harness, CI. | Source tree, [ARCHITECTURE](ARCHITECTURE.md), GitHub Actions run |
| **4. Performance** | Reproducible benchmark with formulas, sample sizes and stated limitations; latency measured separately for the deterministic scan and end-to-end. | `backend/benchmark/results/latest.json`, Scorecard page |
| **5. Google Technology Used** | **Implemented:** Gemini API (multimodal input, structured output, usage metadata for cost) via the `google-genai` SDK. **Optional stretch:** Cloud Run. **Future / not implemented:** Firebase Auth, BigQuery, Cloud Storage, Cloud DLP. | `backend/app/extraction/gemini.py`, README "Google technology" table |

## 13. Short hackathon pitch

> Small businesses pay invoices they have never really checked. **InvoiceGuard+** reads an invoice with Gemini, then lets plain, tested code do the checking: GSTIN checksums, tax arithmetic, duplicates. It returns evidence-backed findings and a transparent risk level, and a human makes the call, with a full audit trail. We do not ask you to trust our AI: our Trust Scorecard shows measured accuracy, false positives, latency, cost and prompt-injection results from a reproducible test suite, with the sample size and limitations printed next to every number.

## 14. Trade-offs against the original brief

| Original idea | Decision | Reason |
|---|---|---|
| BigQuery, Cloud DLP, Cloud Storage, Firebase Auth in the build | Moved to Future | Setup cost exceeds the three-hour budget; claiming them would be unverifiable. |
| "Chat with your data" via LLM-generated SQL | Optional, redesigned as LLM → validated filter JSON → server-built parameterised SQL | Removes the risk of LLM-authored SQL and of the LLM enforcing authorisation. |
| "Verify the GSTIN is active" | Replaced by "format + checksum only" | No offline source can prove registration status. |
| "Confidence scores" | Replaced by uncertainty heuristics | The API gives no calibrated per-field confidence. |
| "Fraud detection" | Reworded to "review signals" | Anomalies and duplicates are not proof of fraud. |
| "Redact PII before the model call" | Replaced by data minimisation (schema excludes bank/phone/address fields) | Redacting an image needs OCR first; Cloud DLP is not integrated. |
| Excel export, Hindi/Marathi | Future | Not needed to prove the core workflow. |
