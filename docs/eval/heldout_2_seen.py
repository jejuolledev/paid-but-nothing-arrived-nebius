# Held-out set 2, written 2026-10-25 by a separate agent that never saw the checker. First run, before any change: wrong caught 26/40, true wrongly rejected 2/15. Time / event-order checks were then added against these misses, so this set is no longer unseen.
# Held-out set 2 for the claim checker. Built only from rows.json (ord_0901..ord_0906).
# WRONG: each sentence is contradicted by the rows it cites. TRUE: each is supported by its cited rows.

WRONG = [
    # ---- ord_0901 ----
    "ok so the customer got charged 29,900 KRW for this one [payments:pay_0901].",  # amount is 24900
    "고객님 결제는 카드 끝자리 4444로 승인된 걸로 보입니다 [payments:pay_0901].",  # card_last4 is 4242
    "It would appear, upon careful review, that the very first webhook attempt for this order was in fact a successful PAID notification [server_logs:2026-10-13T12:00:05Z@/api/payments/webhook].",  # first attempt was FAILED (card declined)
    "first webhook bounced w/ a 402 from our side, card declined [server_logs:2026-10-13T12:00:05Z@/api/payments/webhook].",  # http_status was 200, not 402
    "The confirm call came back 504 because the grant batch timed out [server_logs:2026-10-13T12:00:44Z@/api/payments/confirm].",  # it was 409, order status failed; skipped PSP re-check
    "확인 API는 PSP 재조회를 수행한 뒤 409를 반환했습니다 [server_logs:2026-10-13T12:00:44Z@/api/payments/confirm].",  # message says it SKIPPED the PSP re-check
    "Notably, the PSP payment record was created at 12:00:05, the same second the order flipped to failed [orders:ord_0901] [payments:pay_0901].",  # payment created 12:00:40, not 12:00:05
    "They were credited once for this order, std30 plan [orders:ord_0901].",  # credited is 0
    "주문 0901은 lite10 상품으로 들어왔고요 [orders:ord_0901].",  # reward_key is std30
    "The PAID webhook arrived on the second attempt, which was before the PSP actually recorded the payment [server_logs:2026-10-13T12:00:41Z@/api/payments/webhook] [payments:pay_0901].",  # webhook 12:00:41 is AFTER payment created 12:00:40 (subtle)

    # ---- ord_0902 ----
    "Payment pay_0902 is still sitting in a pending state on the PSP side, so nothing was captured [payments:pay_0902].",  # payment status PAID
    "the checkout for 0902 kicked off around 8 in the morning UTC [server_logs:2026-10-15T20:00:00Z@/api/checkout/start].",  # 20:00 UTC = 8 PM, not morning
    "고객님 주문은 이미 paid 상태로 바뀌어 있습니다 [orders:ord_0902].",  # order status pending
    "The customer paid ₩9,900 using card ending 4242 [payments:pay_0902].",  # card_last4 4444 (subtle, amount right)
    "We received the PSP webhook for ord_0902 and our endpoint responded with a 500 error [server_logs:2026-10-15T20:00:31Z@/api/payments/webhook].",  # http_status 200
    "This order is for the fam60 bundle at 9,900 won [orders:ord_0902].",  # reward_key lite10

    # ---- ord_0903 ----
    "Only a single grant row exists for ord_0903, so there's no double-crediting here [grants:g_ord_0903] [grants:g_ord_0903_retry].",  # two grant rows exist
    "The retry grant gave the customer thirty extra credits [grants:g_ord_0903_retry].",  # credits 60
    "결제 금액은 사만 구천구백 원이었습니다 [payments:pay_0903].",  # 44,900원 (사만 사천구백), not 49,900 (subtle)
    "The confirm endpoint timed out after 30 seconds and, importantly, no grant row was written [server_logs:2026-10-17T01:01:10Z@/api/payments/confirm].",  # 60s, and row WAS written
    "confirm returned a 409 conflict for 0903 [server_logs:2026-10-17T01:01:10Z@/api/payments/confirm].",  # http 504
    "The manual retry was triggered through /api/payments/confirm a couple of minutes later [server_logs:2026-10-17T01:03:00Z@/api/admin/grants/retry].",  # route is /api/admin/grants/retry
    "The credit email to sora.kim903 bounced [mail_events:m_ord_0903@delivered].",  # event delivered
    "메일은 재지급보다 먼저, 01:01 즈음 발송되었습니다 [mail_events:m_ord_0903@sent] [grants:g_ord_0903_retry].",  # sent 01:03:05, after retry grant 01:03:00
    "The first grant was created at 01:03:00, and the retry came before it at 01:01:10 [grants:g_ord_0903] [grants:g_ord_0903_retry].",  # reversed ordering
    "The payment for ord_0903 was charged in USD [payments:pay_0903].",  # currency KRW

    # ---- ord_0904 ----
    "Mail send failed with a 503 because the provider was rate limiting us [server_logs:2026-10-18T18:00:09Z@/api/mail/send].",  # 500, missing API key
    "고객님께 크레딧 30개가 지급되었습니다 [grants:g_ord_0904].",  # credits 10
    "So the confirm step errored out and credits never got granted for noah [server_logs:2026-10-18T18:00:06Z@/api/payments/confirm].",  # 200, credits granted
    "The order itself shows credited = 0, meaning the grant never landed on the order [orders:ord_0904].",  # credited 1
    "The grant for 0904 was written a full minute after confirm, at 18:01:08 [grants:g_ord_0904].",  # created 18:00:08 (subtle)
    "the mail send attempt happened before the confirm call even ran [server_logs:2026-10-18T18:00:09Z@/api/mail/send] [server_logs:2026-10-18T18:00:06Z@/api/payments/confirm].",  # mail 18:00:09 after confirm 18:00:06

    # ---- ord_0905 ----
    "A payment id, pay_0905, is attached to this order, so the charge did go through [orders:ord_0905].",  # payment_id null
    "주문 0905는 결제 완료(paid) 상태이고 금액은 9,900원입니다 [orders:ord_0905].",  # pending, 24900
    "Checkout for 0905 started on October 21st and failed with a 400 [server_logs:2026-10-20T05:00:00Z@/api/checkout/start].",  # 2026-10-20, status 200

    # ---- ord_0906 ----
    "The PSP has the customer's email recorded with the same exmaple.com typo as the order [payments:pay_0906].",  # payment customer_email is example.com (subtle)
    "The confirmation email was sent to liam.patel906@example.com and delivered fine [mail_events:m_ord_0906@bounced].",  # to exmaple.com, event bounced
    "메일 큐 등록은 200이 아니라 500 에러로 실패했습니다 [server_logs:2026-10-20T17:00:29Z@/api/mail/send].",  # 200, credit mail queued
    "The bounce came in about three minutes after the send, so a delayed bounce [mail_events:m_ord_0906@sent] [mail_events:m_ord_0906@bounced].",  # 3 seconds (17:00:30 -> 17:00:33) (subtle)
    "Grant g_ord_0906 put 30 credits onto liam.patel906@example.com, the correctly spelled address [grants:g_ord_0906].",  # grant email is exmaple.com (subtle)
]

TRUE = [
    "Basically the PSP shows pay_0901 as PAID for 24,900 KRW, card ending 4242 [payments:pay_0901].",  # matches payment row
    "The first webhook attempt reported a card decline, yet our endpoint still answered 200 [server_logs:2026-10-13T12:00:05Z@/api/payments/webhook].",  # FAILED card declined attempt 1, http 200
    "확인 요청은 주문이 failed 상태라서 PSP 재조회를 건너뛰고 409를 돌려줬습니다 [server_logs:2026-10-13T12:00:44Z@/api/payments/confirm].",  # 409, skipped re-check
    "No credits were applied to ord_0901, which is still marked failed [orders:ord_0901].",  # credited 0, status failed
    "For ord_0902 the PSP webhook came in as PAID about thirty-one seconds after checkout started [server_logs:2026-10-15T20:00:00Z@/api/checkout/start] [server_logs:2026-10-15T20:00:31Z@/api/payments/webhook].",  # 20:00:00 -> 20:00:31
    "고객님 주문 0902는 아직 pending이고 크레딧은 지급되지 않았어요 [orders:ord_0902].",  # pending, credited 0
    "Two separate grant rows of 60 credits each were written for ord_0903, so the customer was effectively double-granted [grants:g_ord_0903] [grants:g_ord_0903_retry].",  # two grants, 60 each
    "The confirm call timed out with a 504 even though the grant row had already been written [server_logs:2026-10-17T01:01:10Z@/api/payments/confirm].",  # message says row was written
    "The credit mail for 0903 was delivered to sora.kim903@example.com at 01:04 UTC [mail_events:m_ord_0903@delivered].",  # delivered 01:04:00
    "Credits were granted on confirm, but then the mail send blew up with a 500 because the provider API key was missing [server_logs:2026-10-18T18:00:06Z@/api/payments/confirm] [server_logs:2026-10-18T18:00:09Z@/api/mail/send].",  # matches both logs
    "noah got 10 credits on the lite10 reward [grants:g_ord_0904].",  # credits 10, lite10
    "주문 0905에는 결제 ID가 없고, 상태는 pending, 금액은 24,900원입니다 [orders:ord_0905].",  # payment_id null, pending, 24900
    "The order was saved with the misspelled domain exmaple.com, whereas the PSP has the customer as example.com [orders:ord_0906] [payments:pay_0906].",  # typo in order, correct in payment
    "The credit email to liam.patel906@exmaple.com bounced roughly three seconds after it was sent [mail_events:m_ord_0906@sent] [mail_events:m_ord_0906@bounced].",  # 17:00:30 -> 17:00:33
    "It was not a mail-queue failure on our side — /api/mail/send returned 200 and queued the credit mail [server_logs:2026-10-20T17:00:29Z@/api/mail/send].",  # 200 credit mail queued
]
