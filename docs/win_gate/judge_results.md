# Blind judge results (2026-10-27), copied from the two judge agents' final reports

## Judge A (bundle A: 1=T 2=M 3=H 4=K 5=Q 6=S 7=P)
Totals: E1 14 (4/3/3/4), E2 17 (5/4/4/4), E3 13 (3/4/4/2), E4 10 (3/2/3/2), E5 14 (4/3/4/3), E6 12 (3/3/3/3), E7 13 (3/4/3/3)
Ranking: 1 E2, 2 E1, 3 E5, 4 E3, 5 E7, 6 E6, 7 E4
E2 weakness: "the evidence is only 16 held-out photos, all synthetic; edited screenshots were checked only against its own ledger, so it is unproven against real customer photos and real fraud attempts."
E4 weakness: "the model only reads the message and explains; the verdict comes from the PayPal API; close to a single API call with an LLM wrapper; web search on the payer raises privacy concerns."

## Judge B (bundle B: 1=P 2=S 3=Q 4=K 5=H 6=M 7=T)
Totals: E1 13 (3/4/3/3), E2 10 (3/2/3/2), E3 16 (4/4/4/4), E4 12 (3/3/3/3), E5 13 (3/4/4/2), E6 17 (5/4/4/4), E7 14 (4/3/3/4)
Ranking: 1 E6, 2 E3, 3 E7, 4 E5, 5 E1, 6 E4, 7 E2
E6 weakness: "only 16 synthetic photos, and a baseline of free OCR + rules scoring 3/16 looks like a strawman; the audience (Korean and Japanese small shops) is narrow, and the many moving parts could confuse a demo viewer."
E4 weakness: "no demo hook and no aha in the first 30 seconds; web search on the payer raises privacy concerns; Nemotron only reads and explains, so the model's role is thin."
