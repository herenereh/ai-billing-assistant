# Azure deployment

Everything runs in one resource group in one region (default `polandcentral`; the Azure for Students
policy allows `polandcentral`, `norwayeast`, `switzerlandnorth`, `uaenorth`).

```
Agent CLI (your machine) ──► API Management (Consumption) ──► Billing API (Container App) ──► PostgreSQL Flexible (B1ms)
                         └─► MCP server (Container App)
Images: Azure Container Registry (Basic), built locally with Docker for linux/amd64 and pushed.
```

| Step | Script | Creates | Est. cost |
|---|---|---|---|
| 1 | `01-foundation.sh` | Provider registrations, resource group | $0 |
| 2 | `02-postgres.sh` | PostgreSQL 16, Burstable B1ms, 32 GiB, no HA | $0 (750 h/month free offer) |
| 3 | `03-images.sh` | Container Registry Basic + 2 images | ~$5/month |
| 4 | `04-container-apps.sh` | Environment (no Log Analytics) + 2 apps, scale to zero | ~$0 (monthly free grant) |
| 5 | `05-seed.sh` | Nothing new: runs the seed inside the API container (`az containerapp exec`) | $0 |
| 6 | `06-api-gateway.sh` | API Management Consumption, v1 API, policies, subscription key | ~$0 (first 1M calls free) |
| 7 | `07-verify.sh` | Nothing: runs gateway checks, writes `docs/logs/gateway_checks.md` | $0 |
| – | `99-teardown.sh` | Deletes the whole resource group | – |

## Run

Prerequisites: Azure CLI logged in (`az login`), `python3`, `curl`. From the repository root:

```bash
bash infra/azure/01-foundation.sh
bash infra/azure/02-postgres.sh
bash infra/azure/03-images.sh
bash infra/azure/04-container-apps.sh
bash infra/azure/05-seed.sh
bash infra/azure/06-api-gateway.sh
bash infra/azure/07-verify.sh
```

Scripts are safe to re-run: existing resources are reused, apps are updated to the current image tag.
Use another region with `LOCATION=norwayeast bash infra/azure/01-foundation.sh` (use the same value for every step).

## Azure for Students limitations found during deployment

| Limitation | Workaround used |
|---|---|
| ACR Tasks blocked (`az acr build` → `TasksOperationsNotAllowed`) | Build locally with `docker buildx --platform linux/amd64 --push` (needs Docker Desktop). `USE_ACR_TASKS=1` restores cloud builds on other subscriptions. |
| Container Apps environment is created as an **express** environment: no managed identity (`ExpressRegistrySystemIdentityNotSupported`) | Registry admin credentials, stored by Container Apps as a secret |
| Express environments have no Container Apps **Jobs** (`ExpressEnvironmentResourceNotSupported`) | Seed runs inside the running API container with `az containerapp exec` |
| Region policy allows only `polandcentral`, `norwayeast`, `switzerlandnorth`, `uaenorth`, `germanywestcentral` | `polandcentral` (B1ms not offered in `germanywestcentral` here) |
| Newer Azure CLI (2.93) renamed PostgreSQL flags | `--zonal-resiliency` instead of `--high-availability`; database created with `db create --server-name --name` |

## Secrets

Generated values (database password, JWT secret, gateway secret, APIM subscription key, resource-name
suffix) are written to `infra/azure/.env.deploy`, which is git-ignored and `chmod 600`. They are passed to
Azure as Container App secrets and APIM secret named values, never baked into images.

## Security design

- **Gateway only**: the Billing API rejects any request without the `X-Gateway-Secret` header (403
  `GATEWAY_REQUIRED`); only APIM adds it. `/health`, `/docs` and `/openapi.json` stay open (no data).
- **JWT at the gateway**: every operation except `POST /auth/login` and `GET /bills` (public per the app
  spec) must carry a valid token; invalid ones are rejected by APIM before reaching the backend. The API
  validates the token again and takes the subscriber identity only from it.
- **Rate limit**: 60 calls/minute per APIM subscription key (on Consumption, `rate-limit` is per key;
  `rate-limit-by-key` is not available).
- **Database**: reachable only from Azure services, TLS required (`sslmode=require`).
- **Fail closed**: with `APP_ENV=production` the API refuses to start without a real `JWT_SECRET` and `DATABASE_URL`.
