# Held-out set 3, written 2026-10-25 by a separate agent that never saw the checker. Never tuned on. Commit 1104a5e: 33/40 caught, 3/20 wrongly rejected; after fixing false rejections seen in a live Zetaris run (not this set): 32/40, 2/20.
# Held-out set 3 for the claim checker. Built only from heldout/rows.json (ord_0901..ord_0906).

WRONG = [
    # ---- ord_0901 ----
    "Order ord_0901 was marked failed because the PSP never confirmed the charge [payments:pay_0901].",  # payment row status is PAID
    "The customer's card ending in 4444 was declined on the first attempt [payments:pay_0901].",  # pay_0901 card_last4 is 4242 (4444 is pay_0902)
    "The PAID webhook for ord_0901 arrived first, and the FAILED webhook came afterwards and overwrote it [server_logs:2026-10-13T12:00:05Z@/api/payments/webhook] [server_logs:2026-10-13T12:00:41Z@/api/payments/webhook].",  # FAILED at 12:00:05 (attempt 1), PAID at 12:00:41 (attempt 2): order reversed
    "The confirm call at 12:00:44 re-checked the PSP and found the payment declined [server_logs:2026-10-13T12:00:44Z@/api/payments/confirm].",  # log says it skipped the PSP re-check (409)
    "ord_0901 주문은 결제 금액 9,900원짜리 lite10 상품입니다 [orders:ord_0901].",  # amount 24900, reward_key std30
    "Hana's order was credited once, so she should already see her 30 credits [orders:ord_0901].",  # credited = 0, status failed
    "The successful payment for ord_0901 was recorded at 12:00:05 [payments:pay_0901].",  # payment created_at 12:00:40
    "ord_0901의 confirm 요청은 HTTP 200으로 정상 처리됐습니다 [server_logs:2026-10-13T12:00:44Z@/api/payments/confirm].",  # http_status 409
    # ---- ord_0902 ----
    "Jun's payment for ord_0902 is still pending at the PSP, so no money has been taken yet [payments:pay_0902].",  # payment status PAID
    "ord_0902 was a std30 order for 24,900 KRW [orders:ord_0902].",  # lite10, 9900
    "We never received a webhook for ord_0902, which is why the order is stuck [server_logs:2026-10-15T20:00:31Z@/api/payments/webhook].",  # PSP webhook PAID was received at 20:00:31
    "ord_0902 결제 웹훅이 HTTP 500 오류로 실패했습니다 [server_logs:2026-10-15T20:00:31Z@/api/payments/webhook].",  # http_status 200
    "The order for ord_0902 was updated to paid at 20:00:31 [orders:ord_0902].",  # status pending, updated_at 20:00:00
    "Jun paid with a card ending in 4242 [payments:pay_0902].",  # card_last4 4444
    "Checkout for ord_0902 started at 20:00:30, right as the payment was captured [server_logs:2026-10-15T20:00:00Z@/api/checkout/start].",  # checkout started at 20:00:00
    # ---- ord_0903 ----
    "Sora received exactly one grant of 60 credits for ord_0903 [grants:g_ord_0903] [grants:g_ord_0903_retry].",  # two granted rows, 120 total
    "The first grant attempt for ord_0903 failed and wrote nothing, so the admin retry was needed [server_logs:2026-10-17T01:01:10Z@/api/payments/confirm].",  # log says row was written despite timeout
    "ord_0903의 confirm은 30초 후 타임아웃 났습니다 [server_logs:2026-10-17T01:01:10Z@/api/payments/confirm].",  # timed out after 60s
    "The credit email for ord_0903 bounced [mail_events:m_ord_0903@delivered].",  # event is delivered
    "Sora's fam60 order cost 24,900 KRW [orders:ord_0903].",  # amount 44900
    "The retry grant for ord_0903 was created at 01:01:10 [grants:g_ord_0903_retry].",  # retry created 01:03:00 (01:01:10 is the first grant)
    "ord_0903 결제 메일은 재지급보다 먼저 발송됐습니다 [mail_events:m_ord_0903@sent] [grants:g_ord_0903_retry].",  # mail sent 01:03:05 after retry grant at 01:03:00
    "The retry grant for ord_0903 was for 30 credits [grants:g_ord_0903_retry].",  # credits 60
    # ---- ord_0904 ----
    "Noah's credits were never granted for ord_0904 [grants:g_ord_0904].",  # grant row status granted, 10 credits
    "The mail for ord_0904 failed because the recipient address was invalid [server_logs:2026-10-18T18:00:09Z@/api/mail/send].",  # cause is missing API key
    "ord_0904 메일 발송 요청은 200으로 성공했습니다 [server_logs:2026-10-18T18:00:09Z@/api/mail/send].",  # http_status 500
    "Noah's order granted 30 credits [grants:g_ord_0904].",  # credits 10 (lite10)
    "The confirm step for ord_0904 returned a 504 timeout [server_logs:2026-10-18T18:00:06Z@/api/payments/confirm].",  # 200, confirmed; credits granted (504 is ord_0903)
    "Noah paid 44,900 KRW with the card ending in 1117 [payments:pay_0904].",  # amount 9900
    "ord_0904 주문은 아직 pending 상태로 남아 있습니다 [orders:ord_0904].",  # status paid, credited 1
    # ---- ord_0905 ----
    "Emma's payment pay_0905 was captured for 24,900 KRW [orders:ord_0905].",  # payment_id is null; no payment
    "ord_0905의 결제 웹훅은 PAID로 들어왔습니다 [server_logs:2026-10-20T05:00:00Z@/api/checkout/start].",  # only log is checkout started
    "Emma's order ord_0905 is marked failed after a card decline [orders:ord_0905].",  # status pending, no decline
    "Emma ordered the lite10 pack [orders:ord_0905].",  # reward_key std30
    "Checkout for ord_0905 started at 17:00:00 on Oct 20 [server_logs:2026-10-20T05:00:00Z@/api/checkout/start].",  # started 05:00:00
    # ---- ord_0906 ----
    "Liam's credit email for ord_0906 was delivered successfully [mail_events:m_ord_0906@bounced].",  # event bounced
    "The mail for ord_0906 went to liam.patel906@example.com and bounced anyway [mail_events:m_ord_0906@sent].",  # to_address is the typo exmaple.com
    "Liam entered his email correctly on the order, liam.patel906@example.com [orders:ord_0906].",  # order email is liam.patel906@exmaple.com
    "ord_0906 메일은 발송 후 1분 뒤에 반송됐습니다 [mail_events:m_ord_0906@sent] [mail_events:m_ord_0906@bounced].",  # sent 17:00:30, bounced 17:00:33 = 3 seconds
    "No credits were granted for ord_0906 because the email bounced [grants:g_ord_0906].",  # grant row granted, 30 credits
]

TRUE = [
    "The PSP shows pay_0901 as PAID for 24,900 KRW, even though our order record says failed [payments:pay_0901] [orders:ord_0901].",  # PAID 24900 KRW; order status failed
    "ord_0901: 첫 번째 웹훅은 카드 거절(FAILED)이었고, 두 번째 시도에서 PAID가 들어왔습니다 [server_logs:2026-10-13T12:00:05Z@/api/payments/webhook] [server_logs:2026-10-13T12:00:41Z@/api/payments/webhook].",  # attempt 1 FAILED card declined, attempt 2 PAID
    "The confirm call returned 409 and did not re-check the PSP because the order was already marked failed [server_logs:2026-10-13T12:00:44Z@/api/payments/confirm].",  # 409, skipped PSP re-check
    "No credits were added for ord_0901 [orders:ord_0901].",  # credited 0
    "Jun's 9,900 KRW payment was captured and the PAID webhook arrived at 20:00:31, but the order is still pending [payments:pay_0902] [server_logs:2026-10-15T20:00:31Z@/api/payments/webhook] [orders:ord_0902].",  # PAID 9900; webhook 20:00:31; pending
    "ord_0902 주문은 아직 크레딧이 지급되지 않았습니다 [orders:ord_0902].",  # credited 0
    "Sora was granted 60 credits twice for ord_0903, once at 01:01:10 and again at 01:03:00 [grants:g_ord_0903] [grants:g_ord_0903_retry].",  # two grants 60 each
    "The confirm call for ord_0903 timed out after 60 seconds with a 504, but the grant row had already been written [server_logs:2026-10-17T01:01:10Z@/api/payments/confirm].",  # matches message
    "An admin manually retried the grant at 01:03:00 and it granted again [server_logs:2026-10-17T01:03:00Z@/api/admin/grants/retry].",  # manual retry; granted again
    "ord_0903 안내 메일은 sora.kim903@example.com으로 01:04:00에 전달됐습니다 [mail_events:m_ord_0903@delivered].",  # delivered at 01:04:00
    "Noah's 10 credits were granted at 18:00:08 [grants:g_ord_0904].",  # credits 10, created 18:00:08
    "The credit email for ord_0904 was never sent: the mail provider returned 500 because of a missing API key [server_logs:2026-10-18T18:00:09Z@/api/mail/send].",  # 500 missing API key
    "ord_0904는 결제 완료(paid) 상태이고 크레딧도 반영됐습니다 [orders:ord_0904].",  # status paid, credited 1
    "ord_0905 has no payment attached at all; its payment_id is empty and it is still pending [orders:ord_0905].",  # payment_id null, pending
    "The only thing logged for ord_0905 is the checkout starting at 05:00:00 [server_logs:2026-10-20T05:00:00Z@/api/checkout/start].",  # checkout started 05:00:00
    "Liam's order email has a typo, 'exmaple.com', while the PSP has his correct address at example.com [orders:ord_0906] [payments:pay_0906].",  # order exmaple vs payment example
    "ord_0906 크레딧 30개는 정상 지급됐습니다 [grants:g_ord_0906].",  # 30 credits granted
    "The credit mail for ord_0906 was sent at 17:00:30 and bounced three seconds later [mail_events:m_ord_0906@sent] [mail_events:m_ord_0906@bounced].",  # 17:00:30 -> 17:00:33
    "Liam paid 24,900 KRW with a card ending in 5556 [payments:pay_0906].",  # amount 24900, card 5556
    "The mail send request for ord_0906 was accepted with HTTP 200 and queued [server_logs:2026-10-20T17:00:29Z@/api/mail/send].",  # 200, credit mail queued
]
