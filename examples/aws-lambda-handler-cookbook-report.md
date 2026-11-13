# AWS Emulator report: aws-lambda-handler-cookbook

- **Emulator version:** 1.0.337 locally (latest release v1.0.338, 2026-11-12); integration suite and Cognito probe run on 1.0.337
- **Checked:** 2026-11-13 · **IaC:** AWS CDK (Python) · **Languages/SDKs:** Python 3.14, boto3, pydynox (AWS SDK for Rust), Powertools for AWS Lambda

## Verdict

**On the emulator with 3 workarounds.** DynamoDB, which is the service's datastore and backs Powertools
idempotency, runs natively. Three things need test-side workarounds:

- Cognito token verification;
- the resources the CDK stack creates;
- AppConfig feature flags.

No service code changed: every workaround lives in test fixtures and the test env. All 34 integration tests pass
on 1.0.337 in about 7 seconds, with no AWS account.

## Run it locally

```bash
make emulator-install   # macOS/Windows: build the Docker image (Docker running); Linux/CI: install the .deb (sudo)
make emulator-start     # starts it and fails unless it's healthy and telemetry is disabled
make integration        # 34 tests, real AWS credentials removed from the environment
make emulator-stop      # state is in memory only: the next start is clean
```

CI does the same in a job with no environment, no `id-token: write` and `contents: read`.

## What the service uses

| Service | Operations / features | Used by | Called by |
| --- | --- | --- | --- |
| DynamoDB | PutItem, GetItem, Query, UpdateItem, DeleteItem | DAL (pydynox), Powertools idempotency (boto3) | app |
| Cognito user pools | sign-in (tests), JWT verification against the pool's JWKS, pre-token-generation V2 trigger (adds `aud` and the `orders/manage` scope) | API auth (Powertools `JWTVerifier`) | app + AWS (trigger) |
| AppConfig | `GetConfiguration` (Powertools `AppConfigStore`) | feature flags | app |
| Lambda, API Gateway, WAF, CloudWatch, IAM | deployed by CDK | runtime and edge | AWS |
| CloudFormation | the CDK deployment | infrastructure | CDK |

## Fit per feature

The scores come from the v1.0.338 `scores.json.gz`. Operation scores count wire-check steps.

| Service / feature | Scores (service behavioral / your ops) | Known gaps hitting it | Probe (version) | Class | Workaround → coverage lost |
| --- | --- | --- | --- | --- | --- |
| DynamoDB CRUD + idempotency | 71% / 75–94% | none matching our calls | 34/34 integration tests pass (1.0.337) | Native | — |
| Cognito token verification | 69% / 74–90% | `cognito-idp-lambda-a-pretokengeneration-v2-trigger-s.md`, `cognito-identity__cognito-idp: the ID token's iss claim is the bare emulator listener`; issues #58, #61, #62 | RS256 and RSA JWKS ✔ (fixed in 1.0.337), `openid-configuration` ✔, `iss` is `https://127.0.0.1:9297/<pool>` ✘, no `aud` ✘, trigger not invoked ✘ (the same Lambda works when invoked directly) | Workaround | Locally minted tokens → the JWKS download from Cognito, Cognito invoking the trigger |
| CDK deploy | CloudFormation 37% / CreateStack 98%, but 3% wire overall | `AWS::CDK::Metadata`, Outputs | not attempted | Workaround | Fixtures create the tables → whether the deployed table config is right |
| AppConfig feature flags | AppConfig 87% / `GetConfiguration` 50%; AppConfigData 100% | `GetConfiguration` returns 501 | 501 (1.0.322) | Workaround | Mocked in tests (as before the emulator) → AppConfig itself |

## Workarounds

1. **Cognito: locally minted tokens.**
   - **What it does:** `tests/integration/tokens.py` generates an RSA key once per test session. It publishes the
     public key to the handlers through `COGNITO_JWKS`, which Powertools `JWTVerifier.cognito(..., jwks=...)` already
     supports. It then signs Cognito-shaped access tokens.
   - **`aud` and scopes** come from calling the real pre-token-generation handler, so the trigger logic stays tested.
   - **Coverage lost:** the JWKS download from Cognito, Cognito invoking the trigger, and the real token format.
   - **Removed when:** the trigger runs at sign-in, which adds `aud` and the scope, and `iss` matches the real
     Cognito format (#58).
2. **CDK resources: created in fixtures.**
   - **What it does:** session fixtures create the two DynamoDB tables with unique names per run, mirroring
     `cdk/service/api_db_construct.py`.
   - **Coverage lost:** the deployed table configuration. e2e covers it.
   - **Removed when:** CloudFormation fidelity is good enough to deploy the stack. Until then, consider deriving the
     fixtures from `cdk synth` so they can't drift from the stack.
3. **AppConfig: mocked.**
   - **What it does:** the integration tests patch the feature-flag fetch, as they did before the emulator.
   - **Coverage lost:** AppConfig itself.
   - **Removed when:** the service moves to AppConfigData, which scores 100% behavioral. That's not probed yet.

## Not emulatable

None for this service. The integration tests call the handlers directly, so the deployed edge (WAF, API Gateway),
IAM and alarms aren't part of them. CDK synth assertions and e2e against a deployed stack cover those, as before.

## Re-check on each release

- Cognito: sign in through a pool with a pre-token-generation V2 trigger. Does the added claim reach the access
  token? Is `iss` the real Cognito format? Is there an `aud`? (Gap file `...pretokengeneration-v2-trigger-s.md`,
  issues #58, #61, #62.)
- AppConfigData: `StartConfigurationSession` and `GetLatestConfiguration` with the service's flags document.
- CloudFormation: the service-level score. If it climbs, try `cdk deploy` to the emulator with real credentials
  removed.

## Security notes

- **Unpinned binary:** only `LTS/latest` is downloadable and there's no published checksum. CI logs `sha256sum` for
  traceability only, and the Linux install runs as root on the runner.
- **Telemetry:** off three ways (`-t off`, `EMULATOR_TELEMETRY=off`, `config.toml`). `make emulator-check` verifies
  it on every start.
- **Credentials:** test runs remove real AWS credentials, and the integration conftest exits unless
  `AWS_ENDPOINT_URL` is local. The CI test job can't assume an AWS role.

## Evidence

- **Scores:** `scores.json.gz` from v1.0.338 (SHA-256 prefix `8e9bdd717121ff06`).
- **Gap files:** the known-gaps folder at `aws/aws-emulator@main` (2026-11-12), sparse checkout of
  `*-dynamodb-*` and `*-cognito-idp-*`. 477 open files matched. 66 HIGH or MEDIUM files name one of the operations
  PutItem, GetItem, Query, UpdateItem, DeleteItem, TransactWriteItems, InitiateAuth or AdminInitiateAuth. The
  integration suite exercises our DynamoDB call shapes, and it passes.
- **Issues:** #58, #61, #62, #63 and #72 are open (Cognito).
- **Probes:**
    - Cognito probe on 1.0.337: RS256 ✔, OpenID configuration ✔, `iss` local ✘, `aud` none ✘, trigger not invoked ✘.
    - Integration suite: 34 passed on 1.0.337.
