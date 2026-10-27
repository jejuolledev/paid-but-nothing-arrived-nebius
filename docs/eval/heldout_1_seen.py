# Held-out set 1, written 2026-10-25 by a separate agent that never saw the checker. First run, before any change: wrong caught 31/40, true wrongly rejected 1/15. The checker was then fixed against these misses, so this set is no longer unseen.
# Held-out claim-checker test set, written only from rows.json (ord_0901..ord_0906).
# Dates in sentences are chosen so UTC and KST give the same calendar day.

WRONG = [
    # ord_0901
    "The customer was charged 24,000 KRW [payments:pay_0901].",  # amount is 24900
    "Payment pay_0901 shows a status of FAILED [payments:pay_0901].",  # payment status is PAID
    "Order ord_0901 is marked as paid in our system [orders:ord_0901].",  # order status is failed
    "주문 ord_0901의 결제는 2026년 10월 14일에 이루어졌습니다 [payments:pay_0901].",  # payment created 2026-10-13
    "The confirm step for ord_0901 succeeded with HTTP 200 [server_logs:2026-10-13T12:00:44Z@/api/payments/confirm].",  # http_status 409
    "The first webhook attempt already reported the payment as PAID [server_logs:2026-10-13T12:00:05Z@/api/payments/webhook].",  # attempt 1 message says FAILED (card declined)
    "The payment was processed in USD [payments:pay_0901].",  # currency KRW
    "30 credits have been added to the account for ord_0901 [orders:ord_0901].",  # credited = 0
    # ord_0902
    "Order ord_0902 was confirmed and is now complete [orders:ord_0902].",  # order status pending
    "고객님은 9,990원을 결제하셨습니다 [payments:pay_0902].",  # amount 9900
    "The payment for ord_0902 was declined by the card issuer [payments:pay_0902].",  # payment status PAID
    "The webhook for ord_0902 returned HTTP 500 [server_logs:2026-10-15T20:00:31Z@/api/payments/webhook].",  # http_status 200
    "주문 ord_0902는 std30 상품 주문입니다 [orders:ord_0902].",  # reward_key lite10
    "The card used for pay_0902 ends in 4242 [payments:pay_0902].",  # card_last4 4444
    "We have already refunded the 9,900 KRW payment [payments:pay_0902].",  # status PAID, no refund
    # ord_0903
    "Three separate credit grants were issued for ord_0903 [grants:g_ord_0903] [grants:g_ord_0903_retry].",  # only two grants
    "Each grant for ord_0903 was for 30 credits [grants:g_ord_0903] [grants:g_ord_0903_retry].",  # each is 60
    "The confirm call for ord_0903 completed normally with a 200 [server_logs:2026-10-17T01:01:10Z@/api/payments/confirm].",  # 504 timeout
    "The confirmation email for ord_0903 bounced [mail_events:m_ord_0903@delivered].",  # event is delivered
    "주문 ord_0903의 결제 금액은 49,900원입니다 [payments:pay_0903].",  # amount 44900
    "Order ord_0903 was never credited [orders:ord_0903].",  # credited = 1
    "The retry grant for ord_0903 was created on October 18 [grants:g_ord_0903_retry].",  # created 2026-10-17
    "ord_0903 결제는 승인되지 않았습니다 [payments:pay_0903].",  # payment status PAID
    # ord_0904
    "The credit email for ord_0904 was sent successfully [server_logs:2026-10-18T18:00:09Z@/api/mail/send].",  # http 500, provider error
    "Noah received 100 credits for this purchase [grants:g_ord_0904].",  # credits 10
    "메일 발송은 타임아웃 때문에 실패했습니다 [server_logs:2026-10-18T18:00:09Z@/api/mail/send].",  # cause is missing API key, not timeout
    "The confirm endpoint returned 409 for ord_0904 [server_logs:2026-10-18T18:00:06Z@/api/payments/confirm].",  # http_status 200
    "Order ord_0904 is still pending [orders:ord_0904].",  # status paid
    "pay_0904 결제 금액은 99,000원입니다 [payments:pay_0904].",  # amount 9900
    "The grant for ord_0904 was recorded under the fam60 reward [grants:g_ord_0904].",  # reward_key lite10
    # ord_0905
    "Order ord_0905 was paid in full [orders:ord_0905].",  # status pending, payment_id null
    "The checkout for ord_0905 failed with an error [server_logs:2026-10-20T05:00:00Z@/api/checkout/start].",  # 200, checkout started
    "ord_0905는 lite10 상품 주문입니다 [orders:ord_0905].",  # reward_key std30
    "The order total for ord_0905 is 29,400 KRW [orders:ord_0905].",  # amount 24900
    "주문 ord_0905는 이미 크레딧이 적립되었습니다 [orders:ord_0905].",  # credited = 0
    # ord_0906
    "The credit email to liam.patel906@exmaple.com was delivered [mail_events:m_ord_0906@bounced].",  # event is bounced
    "The grant for ord_0906 went to liam.patel906@example.com [grants:g_ord_0906].",  # grant email is ...@exmaple.com
    "주문 ord_0906에는 60크레딧이 지급되었습니다 [grants:g_ord_0906].",  # credits 30
    "The mail send call for ord_0906 failed with HTTP 500 [server_logs:2026-10-20T17:00:29Z@/api/mail/send].",  # http_status 200, queued
    "Payment pay_0906 was refunded to the card ending 5556 [payments:pay_0906].",  # status PAID, no refund
]

TRUE = [
    "The customer was charged 24,900 KRW on the card ending 4242 [payments:pay_0901].",  # amount, currency, card_last4 match
    "Order ord_0901 is still marked as failed and no credits were added [orders:ord_0901].",  # status failed, credited 0
    "결제 확인 단계는 주문 상태가 failed라서 409로 거절되었습니다 [server_logs:2026-10-13T12:00:44Z@/api/payments/confirm].",  # 409, 'order status is failed'
    "The payment provider shows pay_0902 as PAID, but the order is still pending [payments:pay_0902] [orders:ord_0902].",  # PAID vs pending
    "ord_0902의 크레딧은 아직 지급되지 않았습니다 [orders:ord_0902].",  # credited 0
    "Two grants of 60 credits each exist for ord_0903 [grants:g_ord_0903] [grants:g_ord_0903_retry].",  # two rows, 60 each
    "The confirm call for ord_0903 timed out with a 504 even though the grant row was written [server_logs:2026-10-17T01:01:10Z@/api/payments/confirm].",  # 504, 'row was written'
    "The confirmation email for ord_0903 was delivered [mail_events:m_ord_0903@delivered].",  # delivered event
    "10 credits were granted for ord_0904 [grants:g_ord_0904].",  # credits 10, granted
    "메일 발송은 API 키 누락으로 500 오류가 났습니다 [server_logs:2026-10-18T18:00:09Z@/api/mail/send].",  # 500, missing API key
    "Order ord_0905 has no payment linked to it and is still pending, so the customer was never charged for it [orders:ord_0905].",  # payment_id null, pending
    "Checkout for ord_0905 was started successfully [server_logs:2026-10-20T05:00:00Z@/api/checkout/start].",  # 200, checkout started
    "The credit email for ord_0906 bounced [mail_events:m_ord_0906@bounced].",  # bounced event
    "The 30 credits went to liam.patel906@exmaple.com, not to the email on the payment, liam.patel906@example.com [grants:g_ord_0906] [payments:pay_0906].",  # grant email vs customer_email differ
    "ord_0906 결제 24,900원은 정상 승인(PAID)되었습니다 [payments:pay_0906].",  # 24900, PAID
]
