# API Gateway checks

- Gateway: `https://apim-billing-na3xi.azure-api.net/api/v1`

### ✅ Public route: GET /bills (Query Bill)

`HTTP 200` (expected 200)

```json
{"subscriberNo":"5551001","month":10,"year":2026,"total":80.0,"paidAmount":0.0,"remainingBalance":80.0,"status":"UNPAID","dueDate":"2026-11-15"}
```

### ✅ Protected route without token: GET /bills/detailed

`HTTP 401` (expected 401)

```json
{"error":{"code":"UNAUTHORIZED","message":"Missing or invalid bearer token (rejected by the API Gateway)"}}
```

### ✅ Protected route with token: GET /bills/detailed

`HTTP 200` (expected 200)

```json
{"subscriberNo":"5551001","month":10,"year":2026,"total":80.0,"paidAmount":0.0,"remainingBalance":80.0,"status":"UNPAID","dueDate":"2026-11-15","usage":{"phoneMinutes":1350,"internetMb":35000,"internetGb":35.0},"charges":{"phoneCharge":10.0,"internetCharge":70.0,"total":80.0},"usageRecords":{"items":[{"id":7,"usageType":"PHONE","events":15,"quantity":150,"unit":"MIN","recordedAt":"2026-11-23T07:25:31.949671+00:00"},{"id":8,"usageType":"PHONE","events":15,"quantity":150,"unit":"MIN","recordedAt":"2026-11-23T07:25:31.949671+00:00"}],"page":1,"pageSize":2,"totalItems":16,"totalPages":8}}
```

### ✅ Forged token rejected at gateway

`HTTP 401` (expected 401)

```json
{"error":{"code":"UNAUTHORIZED","message":"Missing or invalid bearer token (rejected by the API Gateway)"}}
```

### ✅ Another subscriber's bill with own token

`HTTP 403` (expected 403)

```json
{"error":{"code":"FORBIDDEN","message":"You can only view your own bill"}}
```

### ✅ Business error passed through: unknown period

`HTTP 404` (expected 404)

```json
{"error":{"code":"BILL_NOT_FOUND","message":"No bill for subscriber 5551001 for 2025-04. Calculate the bill first."}}
```

### ✅ Missing APIM subscription key

`HTTP 401` (expected 401)

```json
{ "statusCode": 401, "message": "Access denied due to missing subscription key. Make sure to include subscription key when making requests to an API." }
```

### ✅ Bypassing the gateway (direct backend call)

`HTTP 403` (expected 403)

```json
{"error":{"code":"GATEWAY_REQUIRED","message":"Call this API through the API Gateway"}}
```

