# MCP retrieval demo

- Server: `https://ca-billing-mcp.nicedune-430dff91.polandcentral.azurecontainerapps.io/mcp`
- Tool: `search_billing_documentation`

## Query 1: “How much does extra internet cost?”

| Rank | Section | Heading | Score |
|---|---|---|---|
| 1 | 8.1 | What is the cost of extra internet? | 6.351 |
| 2 | 3.2 | Additional internet blocks | 3.28 |
| 3 | 4.3 | Worked example | 2.865 |

<details><summary>Raw tool result</summary>

```json
{
  "document": "Mobile_Provider_Billing_Guide.md",
  "document_id": "MOB-BILLING-2026-01",
  "query": "How much does extra internet cost?",
  "matches": [
    {
      "section": "8.1",
      "heading": "What is the cost of extra internet?",
      "parent_heading": "Frequently asked questions",
      "text": "Each additional 10 GB block beyond 20 GB costs $10. Partially used blocks are rounded up. See Section 3.2.",
      "score": 6.351
    },
    {
      "section": "3.2",
      "heading": "Additional internet blocks",
      "parent_heading": "Internet pricing",
      "text": "Each additional 10 GB block costs $10. A partially used additional block is charged as a full block. For example, 20 GB costs $50; 21 GB costs $60; 30 GB costs $60; 35 GB costs $70.",
      "score": 3.28
    },
    {
      "section": "4.3",
      "heading": "Worked example",
      "parent_heading": "Bill calculation",
      "text": "A subscriber uses 1,350 phone minutes and 35 GB of internet in a month. Phone: $10 for one extra 1,000-minute block. Internet: $50 base + $20 for two additional 10 GB blocks. Total = $80.",
      "score": 2.865
    }
  ]
}
```

</details>

## Query 2: “Can I pay only part of my bill?”

| Rank | Section | Heading | Score |
|---|---|---|---|
| 1 | 8.3 | Can I pay only part of my bill? | 9.45 |
| 2 | 5.3 | Payment result | 4.4 |
| 3 | 5.1 | Full and partial payments | 2.065 |

<details><summary>Raw tool result</summary>

```json
{
  "document": "Mobile_Provider_Billing_Guide.md",
  "document_id": "MOB-BILLING-2026-01",
  "query": "Can I pay only part of my bill?",
  "matches": [
    {
      "section": "8.3",
      "heading": "Can I pay only part of my bill?",
      "parent_heading": "Frequently asked questions",
      "text": "Yes. The unpaid remainder stays outstanding, and the bill is not fully paid until the balance reaches zero. See Section 5.1.",
      "score": 9.45
    },
    {
      "section": "5.3",
      "heading": "Payment result",
      "parent_heading": "Payments and outstanding balances",
      "text": "The assistant should report success only after the Pay Bill API confirms the transaction. Retries should use idempotency protection to avoid duplicate payment records.",
      "score": 4.4
    },
    {
      "section": "5.1",
      "heading": "Full and partial payments",
      "parent_heading": "Payments and outstanding balances",
      "text": "Subscribers may make full or partial payments. A partial payment reduces the outstanding balance but does not mark the bill fully paid.",
      "score": 2.065
    }
  ]
}
```

</details>

## Query 3: “What happens if I pay late?”

| Rank | Section | Heading | Score |
|---|---|---|---|
| 1 | 6.2 | Late payment reminder | 4.635 |
| 2 | 6.1 | Due date | 2.821 |
| 3 | 6.3 | Service restriction | 2.651 |

<details><summary>Raw tool result</summary>

```json
{
  "document": "Mobile_Provider_Billing_Guide.md",
  "document_id": "MOB-BILLING-2026-01",
  "query": "What happens if I pay late?",
  "matches": [
    {
      "section": "6.2",
      "heading": "Late payment reminder",
      "parent_heading": "Late payments and restrictions",
      "text": "An unpaid bill may trigger a reminder after its due date. The reminder itself does not add a fee.",
      "score": 4.635
    },
    {
      "section": "6.1",
      "heading": "Due date",
      "parent_heading": "Late payments and restrictions",
      "text": "A monthly bill is due 15 calendar days after the end of its billing month. For example, an October 2026 bill is due November 15, 2026.",
      "score": 2.821
    },
    {
      "section": "6.3",
      "heading": "Service restriction",
      "parent_heading": "Late payments and restrictions",
      "text": "Service may be restricted when a bill remains unpaid for 30 days after the due date, subject to customer support review. This is a policy description, not a live service-status check.",
      "score": 2.651
    }
  ]
}
```

</details>
