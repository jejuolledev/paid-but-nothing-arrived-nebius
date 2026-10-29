# Measurements (Nebius Token Factory version)

| when | set | reader | sender | order nos. | amount | complaint | right order + link | plan reached it | dropped values | failed calls | avg model ms/msg | tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-27 21:48 | heldout (40) | rules, no model | 38/40 | 40/40 | 39/40 | — | 38/40 | — | 0 | 0 | 0 | 0 |
| 2026-10-27 21:48 | dev (12) | rules, no model | 10/12 | 12/12 | 11/12 | — | 10/12 | — | 0 | 0 | 0 | 0 |
| 2026-10-27 22:31 | heldout (40) | rules, no model | 38/40 | 40/40 | 39/40 | — | 38/40 | — | 0 | 0 | 0 | 0 |
| 2026-10-27 22:35 | fallback_dev (8) | rules, no model | 6/8 | 8/8 | 8/8 | — | 5/8 | — | 0 | 0 | 0 | 0 |
| 2026-10-27 22:35 | fallback_heldout (22) | rules, no model | 16/22 | 22/22 | 21/22 | — | 17/22 | — | 0 | 0 | 0 | 0 |
| 2026-10-29 15:51 | fallback_dev (8) | model nvidia/Nemotron-3_5-Lightning (Ultra re-read when unsure: nvidia/Nemotron-3-Ultra-550b-a55b) | 6/8 | 8/8 | 8/8 | 8/8 | 5/8 | 5/8 | 2 | 0 | 9379 | 35440 |
| 2026-10-29 15:52 | fallback_dev (8) | model nvidia/Nemotron-3_5-Lightning (Ultra re-read when unsure: nvidia/Nemotron-3-Ultra-550b-a55b) | 6/8 | 8/8 | 8/8 | 8/8 | 5/8 | 5/8 | 4 | 0 | 9495 | 35524 |
| 2026-10-29 15:53 | dev (12) | rules, no model | 10/12 | 12/12 | 11/12 | — | 11/12 | — | 0 | 0 | 0 | 0 |
| 2026-10-29 15:53 | heldout (40) | rules, no model | 38/40 | 40/40 | 39/40 | — | 38/40 | — | 0 | 0 | 0 | 0 |
| 2026-10-29 15:53 | fallback_dev (8) | rules, no model | 6/8 | 8/8 | 8/8 | — | 5/8 | — | 0 | 0 | 0 | 0 |
| 2026-10-29 15:53 | fallback_heldout (22) | rules, no model | 16/22 | 22/22 | 21/22 | — | 18/22 | — | 0 | 0 | 0 | 0 |
| 2026-10-29 15:54 | fallback_dev (8) | model nvidia/Nemotron-3_5-Lightning (Ultra re-read when unsure: nvidia/Nemotron-3-Ultra-550b-a55b) | 6/8 | 8/8 | 8/8 | 8/8 | 5/8 | 4/8 | 3 | 0 | 7796 | 35255 |
| 2026-10-29 15:55 | dev (12) | rules, no model | 10/12 | 12/12 | 11/12 | — | 11/12 | — | 0 | 0 | 0 | 0 |
| 2026-10-29 15:55 | heldout (40) | rules, no model | 38/40 | 40/40 | 39/40 | — | 38/40 | — | 0 | 0 | 0 | 0 |
| 2026-10-29 15:55 | fallback_dev (8) | rules, no model | 6/8 | 8/8 | 8/8 | — | 6/8 | — | 0 | 0 | 0 | 0 |
| 2026-10-29 15:55 | fallback_heldout (22) | rules, no model | 16/22 | 22/22 | 21/22 | — | 21/22 | — | 0 | 0 | 0 | 0 |
| 2026-10-29 15:57 | fallback_dev (8) | model nvidia/Nemotron-3_5-Lightning (Ultra re-read when unsure: nvidia/Nemotron-3-Ultra-550b-a55b) | 8/8 | 8/8 | 8/8 | 8/8 | 7/8 | 7/8 | 0 | 0 | 12640 | 40909 |
| 2026-10-29 16:03 | fallback_heldout (22) | model nvidia/Nemotron-3_5-Lightning (Ultra re-read when unsure: nvidia/Nemotron-3-Ultra-550b-a55b) | 20/22 | 22/22 | 21/22 | 16/22 | 20/22 | 12/22 | 7 | 0 | 15540 | 113794 |
| 2026-10-29 16:11 | heldout (40) | model nvidia/Nemotron-3_5-Lightning (Ultra re-read when unsure: nvidia/Nemotron-3-Ultra-550b-a55b) | 40/40 | 39/40 | 40/40 | 29/40 | 40/40 | 35/36 | 3 | 1 | 12258 | 173463 |

Note (2026-10-29 17:30): after these runs, QA found that without a reader (no key, past the live limit, a failed
call) the agent still took the first of several addresses. Commit fe93495 makes that path read nobody's records
instead. The rules rows above are the old regex baseline and are reproduced with `first_address_rule=True`
(re-run after the change: same 38/40, 16/22 · 21/22, 6/8 · 6/8, 10/12 · 11/12). The model rows were not re-run.
### Turn-by-turn mode (the model picks each lookup; `AGENT_MODE=loop`), added 2026-10-29 evening
A second configuration, measured once on the same held-out set after the plan-mode run above. The message reader's prompt is unchanged since that run; other code changed in between (the no-guess sender rule, reply wording; see git log).

| when | set | reader | sender | order nos. | amount | complaint | right order + link | plan reached it | dropped values | failed calls | avg model ms/msg | tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-29 19:15 | fallback_dev (8) | model nvidia/Nemotron-3_5-Lightning (Ultra re-read when unsure: nvidia/Nemotron-3-Ultra-550b-a55b) + turn-by-turn lookups (agent_loop, the model picks each lookup) | 7/8 | 8/8 | 7/8 | 5/8 | 6/8 | 5/8 | 3 | 0 | 15915 | 67372 |
| 2026-10-29 19:35 | fallback_heldout (22) | model nvidia/Nemotron-3_5-Lightning (Ultra re-read when unsure: nvidia/Nemotron-3-Ultra-550b-a55b) + turn-by-turn lookups (agent_loop, the model picks each lookup) | 21/22 | 22/22 | 20/22 | 16/22 | 21/22 | 21/22 | 4 | 0 | 17505 | 205120 |
