# Agent scenarios

- Run at: 2026-11-22T14:31:12+00:00
- LLM provider: `rule-based`
- Billing API: `http://localhost:8000/api/v1`
- MCP server: `http://127.0.0.1:8001/mcp`
- Logged in as: `5551001`

## MCP only

```text
you> How much does extra internet cost?
  [tool] search_billing_documentation(query=How much does extra internet cost?, top_k=3) -> ok: sections 8.1, 3.2, 4.3
assistant> From the Billing Guide (MOB-BILLING-2026-01):
• §8.1 What is the cost of extra internet?: Each additional 10 GB block beyond 20 GB costs $10. Partially used blocks are rounded up. See Section 3.2.
• §3.2 Additional internet blocks: Each additional 10 GB block costs $10. A partially used additional block is charged as a full block. For example, 20 GB costs $50; 21 GB costs $60; 30 GB costs $60; 35 GB costs $70.

```

## API only

```text
you> What is my October bill?
  [tool] query_bill(month=10, year=2026) -> ok: total 80.0, remaining 80.0, UNPAID
assistant> Your October 2026 bill is $80.00. Paid: $0.00, remaining: $80.00 (status UNPAID). Due date: 2026-11-15.

```

## API + MCP

```text
you> Why is my October bill higher?
  [tool] query_bill_detailed(month=10, year=2026) -> ok: total 80.0, 1350 min, 35.0 GB
  [tool] query_bill_detailed(month=9, year=2026) -> ok: total 50.0, 800 min, 18.0 GB
  [tool] search_billing_documentation(query=additional internet blocks additional minutes pricing bill higher, top_k=4) -> ok: sections 2.2, 3.2, 4.3, 9
assistant> Your October 2026 bill is $80.00: phone $10.00 for 1,350 minutes and internet $70.00 for 35 GB.
That is $30.00 more than September 2026 ($50.00: 800 minutes, 18 GB).
Phone: the first 1,000 minutes are free and each started extra 1,000-minute block costs $10 (Billing Guide §2.2). You used 350 minutes over the free allowance.
Internet: $50 covers up to 20 GB and each started extra 10 GB block costs $10 (Billing Guide §3.2). You were 15 GB over 20 GB, which is why internet cost $70.00.

```

## Payment with explicit confirmation

```text
you> Pay my bill
  [tool] pay_bill(month=10, year=2026) -> ok: awaiting confirmation for $80.0
assistant> Please confirm this payment:
  Subscriber: 5551001
  Bill:       October 2026
  Amount:     $80.00 (remaining balance $80.00)
Reply 'yes' to pay or 'no' to cancel.

you> yes
  [tool] pay_bill(month=10, year=2026, amount=80.0, transactionId=agent-fcf5e66ad82e40a48cd8) -> ok: SUCCESS, remaining 0.0
assistant> Payment successful: $80.00 paid for your October 2026 bill (transaction agent-fcf5e66ad82e40a48cd8). Remaining balance: $0.00, status PAID.

```
