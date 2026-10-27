# Demo video — narration and shot list (target 2:00, English)

Lines are numbered for TTS (one audio file per line: N01.wav …). Times are targets; the edit follows the audio.

| # | Time | Picture | Narration |
|---|---|---|---|
| N01 | 0:00 | Customer message card (phone style), red | “I paid 24,900 won and nothing arrived. I’m filing a chargeback.” Every small online seller knows this message. |
| N02 | 0:07 | Comic panels 1–2 (night desk, four dashboards) | The proof is in four places: the payment provider, the orders database, the server logs, the mail provider. At one in the morning, that’s four dashboards. |
| N03 | 0:16 | App: paste only the customer’s email, press Investigate | Paste the message. Just the customer’s email — no order number. |
| N04 | 0:21 | Investigation timeline steps appear one by one; receipt line visible | Nemotron, through Meterless Nightshift, decides where to look. No order under this email. So: who paid at the payment provider? Which order is that payment? Then the full journey. Every lookup is read-only, through one SQL door — Zetaris. |
| N05 | 0:42 | Chain: three green, two red; click a citation, the row flashes | A rule-based verifier — not the model — checks the money chain. Paid. Order confirmed. But the credits went to a typo — exmaple dot com — and the mail bounced. Every red link carries the rows that prove it. |
| N06 | 1:00 | Reply card (Korean toggle briefly) and fix card | You get a reply in the customer’s language. It can’t promise refunds — money is a human decision. And a fix: move the credits, once the customer confirms. |
| N07 | 1:12 | Approve → confirm dialog → chain turns green; “Fixed by you” before/after | Approve, and the fix runs. The chain turns green, and the fix goes into an audit log. |
| N08 | 1:21 | Case 5: grey chain, “You were never charged” | And when nothing is broken, it says so: you were never charged. |
| N08b | 1:26 | Same result: the yellow note “ord_0903 belongs to another customer, so it was not read” | And if a message quotes someone else's order number, that order is never read. |
| N09 | 1:28 | Zetaris: registered datasources and the order_journey layer; Nightshift Apps panel and a receipt | Under the hood: the shop's five record tables are registered in Zetaris and joined in one semantic layer, order journey. Every model call goes through Nightshift, with a receipt for which model ran. Addresses are masked and card digits removed before any row reaches the model. |
| N10 | 1:46 | Measurements card | Six cases, rebuilt from real bugs in our own shop with synthetic data: six out of six right, every explanation cited. |
| N11 | 1:55 | How-it-works picture, then title | Paid, but nothing arrived? Found in one pass. |

Notes
- No model wait on screen: cut the “investigating…” stretches; keep the step lines appearing.
- Burned-in subtitles for every line (the video must make sense muted).
- Sponsor badges in the corner throughout: Zetaris · Meterless Nightshift · NVIDIA Nemotron · built with Cursor.
