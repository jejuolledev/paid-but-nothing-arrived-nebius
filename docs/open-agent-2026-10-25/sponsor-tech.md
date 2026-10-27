# Sponsor technologies — how each one is used

## How Zetaris was integrated
Zetaris is the only thing the agent queries. The four systems a seller would otherwise open by hand — the payment-provider ledger, the orders and credit-grants database, the server-log export and the mail-provider events — are stood in for by three separate synthetic databases, each registered in Zetaris as its own datasource (local Zetaris platform, Lightning JDBC; `zetaris/register.sql`):

| Zetaris datasource | stands in for | tables |
|---|---|---|
| `demo_pg` | the shop's app database | orders, grants, server_logs |
| `psp_pg` | the payment provider's ledger | payments |
| `mail_pg` | the mail provider's events | mail_events |

All five tables are activated into one unified semantic layer, `order_journey`. For an order's full history the agent sends **one SQL statement** that joins the five tables across the three datasources (`agent/tools.py`, `order_journey`); Zetaris federates it, nothing is copied out of the sources, and the joined rows are split back into per-source rows so each one keeps its `table:key` ref. The page shows that statement above the evidence rows, and the SQL behind every step of the investigation (`docs/demo/zetaris_ui/30_journey_query_in_zetaris.png` is the same joins run by hand in Zetaris's SQL Workspace, with a shorter column list; `31_three_datasources.png` is `SHOW DATASOURCES`).

- Measured on the local platform: the journey query takes about 6–9 s warm (Docker on an Apple-silicon laptop).

- Read-only by design. When the seller approves a fix, Zetaris is not written to: the fix belongs to the seller's own systems. In the offline demo (DuckDB over the same synthetic CSVs, same table names, same SQL) the fix is applied so the chain can be seen turning green; on Zetaris the approve endpoint answers "read-only" instead of pretending.

## How Meterless was integrated
Every model call goes to Meterless Nightshift's OpenAI-compatible Runtime on the seller's Mac (`http://127.0.0.1:8088/v1`, key read from Nightshift's own token file). The app identifies itself (`meterless-app: paid-but-nothing-arrived`), so the seller can see and bind its routing in Nightshift's Apps panel. Nightshift seats an **NVIDIA Nemotron 3.5 Lightning** lane on the seller's NVIDIA key (in the demo, NVIDIA's hosted endpoint) and returns a compute receipt with every answer (which model ran, under which mode). The agent keeps those receipts per step and shows them on screen next to its own checks.

- The agent refuses any model endpoint that is not on this machine unless `ALLOW_CLOUD_LLM=1`; Nightshift is that local endpoint, and what Nightshift may route to is the seller's choice in Nightshift (privacy floor: local-only / cloud-ok). In the demo the floor is cloud-ok, so masked rows reach NVIDIA's hosted endpoint; names or phone numbers typed in a customer's message are not masked.
- Before any row reaches the model, the sender's address becomes `CUSTOMER`, other addresses keep only a first letter and the domain (so a typo like `exmaple.com` stays visible), and card digits are removed.

## Where NVIDIA technology contributes
NVIDIA Nemotron does two jobs, and decides neither the verdict nor the fix:
1. **Investigates.** Given the customer's message, it chooses which read-only tool to call next (find the customer's orders, find payments made by their address, find the order behind a payment, pull a full journey). Case 6 — paid with one address, ordered under a typo of it — is found this way in four tool calls. (Offline, a fixed fallback lookup — payer address → payment provider → order — also reaches it; the model's job is to choose the path when the message does not fit that one.) The tools only follow the trail of the address in the message, and an order number that belongs to a different address is ignored and shown as ignored (tested, and probed in every measurement run). The seller still confirms that the address is the real sender's.
2. **Explains and drafts.** It writes the explanation (which must cite the rows it used, or it is replaced by the verifier's text) and the reply to the customer, in the customer's language; a reply that promises money is replaced by a template.

Measured on the local Zetaris platform in six runs (logs in `docs/measurements_2026-10-2*_zetaris.log`) through Nightshift → Nemotron 3.5 Lightning (hosted NIM, free trial key): right order and broken link 6/6 in every run, cross-customer probe blocked in every run. Final code (01:52): the loop named the order 6/6 (case 6 from the payer's email alone), every explanation the model returned passed the per-sentence check (5/5; one call failed at the free endpoint and is labelled), and on sentences written by a separate model that never saw the checker it catches 32/40 wrong ones and wrongly rejects 2/20 true ones. 83–271 s per case on the free endpoint. An earlier version of the pipeline (five cases, before the investigation loop) also ran fully on the Mac with Nemotron 3.5 Lightning 30B 4-bit through rapid-mlx: 5/5 and 5/5, ~14 s per case.

## How Cursor was used
The repository was developed with Cursor's agent (`cursor-agent`) alongside hand-written code. Project rules live in `.cursor/rules/project.mdc` (cite-or-fail, single SQL door, verifier decides, human approval for fixes, synthetic data only). Commits made through Cursor are marked `[cursor-agent]`, and the session outputs are saved in `docs/cursor-sessions/` (UI overhaul, approve-and-fix with audit log, Korean replies, Nightshift receipts on screen, the how-it-works strip, the result layout). Every Cursor change was reviewed and tested before it was committed.

## What was unique
- The agent can say "nothing is broken — you were never charged", and proves it.
- The model investigates, but a deterministic verifier decides; every red link carries the rows that prove it.
- A human approves every fix; every approved fix is written to an audit log; a fix that would move credits to another address first asks for the customer's confirmation.
- The cases are incidents from our own small shop, rebuilt with synthetic data.
