# AWS Emulator Adoption Skill

An agent skill that sets up [AWS Emulator](https://docs.aws.amazon.com/emulator/latest/userguide/) for your
serverless service and tells you, with evidence, whether the service can run fully on the emulator or needs
workarounds. It writes the answer to a report file in your repo.

> Point your coding agent at a repo and ask *"can this service run on AWS Emulator?"*. You get the setup files, a
> per-feature verdict and `aws-emulator-report.md`.

## What is AWS Emulator?

[AWS Emulator](https://github.com/aws/aws-emulator) is a local emulator of AWS service APIs, published by AWS. It's
a single command, `aws-emulator`, that serves AWS APIs over HTTPS on `127.0.0.1:9297`.

- **Works with your existing code.** The AWS CLI and every AWS SDK talk to it through the standard
  `AWS_ENDPOINT_URL`, plus the credentials, config and CA files it generates at start. It's not an in-process mock,
  so it works from any language: Python, JavaScript, Java, Go, Rust and .NET.
- **Runs anywhere.** It runs natively on Linux (Debian and RPM packages), in Docker on macOS and Windows, and
  embedded in Rust tests.
- **No AWS account.** Integration tests run in seconds on a laptop or a CI runner without credentials, so an AI
  agent can run them on its own, with no way to touch a real account.
- **Moves fast, and isn't complete.** New releases ship every few days. Each release publishes fidelity scores per
  service, and the repo keeps thousands of
  [known-gap reports](https://github.com/aws/aws-emulator/tree/main/issues/things-that-do-not-work). Some services
  are close to AWS; others are thin. Which ones your service uses decides whether your tests still prove anything.

That last point is why this skill exists.

## Why this skill?

Moving integration tests from a deployed stack to an emulator is a trade:

| You gain | You pay |
| --- | --- |
| Integration runs in seconds, not after a long deploy | Every unsupported feature becomes a workaround |
| Agentic development with no AWS credentials in reach | Every workaround is code that no longer runs in your integration tests |
| Faster, credential-free CI that stops before deploying | A green run proves less, and you have to know exactly what |

The skill makes the trade explicit. It finds every AWS feature your service relies on, checks each against the
emulator's real gap data, **probes the risky ones on the latest build**, and tells you what runs natively, what
needs a workaround (and the coverage that costs), and what has to stay in e2e.

## What the skill does

1. **Checks your environment:** OS, CPU, Docker, port, latest emulator release, your task runner and IaC tool.
2. **Installs and runs the emulator locally.** It writes:
    - a Dockerfile for macOS and Windows, and the Debian package install for Linux and CI;
    - a config with telemetry off, verified on every start;
    - an env file that removes real AWS credentials;
    - task-runner targets (`emulator-install`, `-start`, `-check`, `-stop`, `integration`), including Windows `cmd`
      notes.
3. **Inventories your service:**
    - **CDK** (`cdk synth`) or **Terraform** (static `aws_*` resources and data sources), plus SAM and the
      Serverless Framework;
    - the services *and operations* your code calls, in Python, JavaScript/TypeScript, Java/Kotlin, Go, Rust and
      .NET;
    - libraries that call AWS for you (Powertools, object mappers, Spring Cloud AWS), and clients that bypass the SDK
      (database drivers, Redis, Kafka, JWKS fetches, hard-coded AWS hosts).
4. **Collects gap evidence** for every service and operation you use:
    - per-release **scores** per service and per operation (a bundled helper reads `scores.json.gz`);
    - the **known-gaps folder** (sparse checkout of only your services, about 2 seconds), indexed by severity and
      operation;
    - **GitHub issues** and **release notes**.
5. **Probes the risky items** on the latest build. Gap lists lag behind fixes and fixes lag behind lists, so it tests
   the *effect*: a trigger that actually runs, a token your verifier actually accepts.
6. **Classifies each feature** as **Native**, **Workaround** or **Not emulatable**, using a catalog of proven
   workarounds. Each one lists the test coverage it costs.
7. **Wires it in:** a test guard that refuses non-local endpoints, credential-free CI jobs and agent permissions.
8. **Writes `aws-emulator-report.md`** in your repo: the verdict, how to run locally, the feature table, the
   workarounds, what to re-check on each release, security notes and the evidence.

### Which languages?

The setup, the gap evidence and the verdict don't depend on your language: the emulator is a network endpoint, and
the gaps are per AWS service and operation. Language-specific support covers finding what your code calls, trusting
the emulator's CA, and failing the test run if it isn't pointed at the emulator:

| Language | Finds services and operations | CA trust | Test guard |
| --- | --- | --- | --- |
| Python | `boto3` clients, `put_item(` → `PutItem` | `AWS_CA_BUNDLE` | pytest `pytest_sessionstart` |
| JavaScript/TypeScript | `@aws-sdk/client-*`, `new PutItemCommand(` | `NODE_EXTRA_CA_CERTS` | Jest / Vitest `globalSetup` |
| Java/Kotlin | `software.amazon.awssdk.services.*`, `PutItemRequest` | truststore from `ca.pem` | JUnit 5 `@BeforeAll` |
| Go | `aws-sdk-go-v2/service/*`, `&dynamodb.PutItemInput{` | `AWS_CA_BUNDLE` | `TestMain` |
| Rust | `aws-sdk-*` crates, `.put_item()` | `SSL_CERT_FILE` | shared client builder (or embedded mode) |
| .NET | `AWSSDK.*` packages, `PutItemAsync(` | `SSL_CERT_FILE` | xUnit module initializer |

It also knows the common libraries for each ecosystem: Powertools (Python, TypeScript, Java and .NET), DynamoDB
object mappers, Spring Cloud AWS, and database, Redis and Kafka clients.

### CDK or Terraform?

Both are supported, and the skill treats them differently:

- **CDK, SAM and CloudFormation** deploy through CloudFormation. Its emulator score is low today, so the skill
  creates your resources in test fixtures, built from `cdk synth`, instead of deploying the stack.
- **Terraform** calls each service's API directly, so `terraform apply` against the emulator can work when every
  service you use scores well. The skill uses a separate local state and checks it first with one cheap resource.

### Safety rules it follows

- Never touches a real AWS account: no deploy, no `terraform apply` against real state, no `aws` CLI calls with real
  credentials.
- Telemetry off in three places, and verified from the startup log.
- Tells you about the supply-chain trade-off: the emulator ships only an unpinned `latest` package with no published
  checksum.

## Install

The skill is one folder: `aws-emulator-adoption/` (`SKILL.md` plus a helper script).

**Claude Code: for all your projects**

```bash
git clone https://github.com/ran-isenberg/aws-emulator-adoption-skill.git
mkdir -p ~/.claude/skills && cp -r aws-emulator-adoption-skill/aws-emulator-adoption ~/.claude/skills/
```

**Claude Code: for one repo** (commit it, so your team gets it too)

```bash
mkdir -p .claude/skills && cp -r aws-emulator-adoption-skill/aws-emulator-adoption .claude/skills/
```

**Other agents:** any agent that loads `SKILL.md`-style skills can use the folder as is. Otherwise, paste `SKILL.md`
into the agent's instructions.

**Requirements:** `git`, `gh` (GitHub CLI), `python3` (for the scores helper, whatever your service's language) and
`jq`. Docker on macOS and Windows; on Linux, a Debian-based
system with `sudo` (or adapt the RPM line).

## Use it

Ask your agent, in the repo you want to check:

- *"Can this service run fully on AWS Emulator, or does it need hacks?"*
- *"Set up AWS Emulator for local integration tests and tell me the gaps."*
- *"A new emulator version is out. Re-check our workarounds and update the report."*

The output is `aws-emulator-report.md` in the repo root. It's meant to be diffed on every emulator release: each fix
upstream should remove a workaround.

## Example

[`examples/aws-lambda-handler-cookbook-report.md`](examples/aws-lambda-handler-cookbook-report.md) is the report for
[AWS Lambda Handler Cookbook](https://github.com/ran-isenberg/aws-lambda-handler-cookbook), a production-grade
Python serverless template: API Gateway, Lambda, DynamoDB, Cognito auth and AppConfig feature flags, deployed with
CDK.

> **Verdict:** on the emulator with 3 workarounds (Cognito tokens, fixture-created resources, mocked AppConfig), and
> no service-code changes. 34 of 34 integration tests pass in about 7 seconds with no AWS account.

That adoption is where this skill came from: every workaround pattern in it was used there first.

## Status

- Not affiliated with or endorsed by AWS. AWS Emulator is an AWS project; see its
  [user guide](https://docs.aws.amazon.com/emulator/latest/userguide/) and
  [repo](https://github.com/aws/aws-emulator).
- The emulator changes every few days. The skill always works from the latest release and live gap data, but the
  example report is a snapshot (November 2026).

## License

[MIT](LICENSE)
