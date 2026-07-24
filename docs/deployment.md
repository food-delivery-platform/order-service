# Deployment — Step Functions + Lambda

Workflow: `.github/workflows/deploy-step-functions.yml`

Trigger: push to `main` branch, or manual (`workflow_dispatch`).

## Required GitHub Secrets

| Secret | Purpose |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user access key for the deployer |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret key for the deployer |
| `AWS_REGION` | AWS region (e.g. `eu-west-1`) |
| `LAMBDA_EXECUTION_ROLE_ARN` | IAM role ARN assigned to Lambda functions |
| `AWS_STEP_FUNCTIONS_ROLE_ARN` | IAM role ARN for Step Functions execution |
| `AWS_STEP_FUNCTIONS_STATE_MACHINE_NAME` | Name of the Step Functions state machine |
| `SERVICE_SECRET_ARN` | ARN of the Secrets Manager secret holding credentials. The **secret value** NEVER enters this secret — only the ARN. |

> **Security note:** The secret **value** is fetched at Lambda runtime via
> `src/shared/config/secrets.py`. It never appears in environment variables,
> logs, CI output, or committed files.

---

## Deployer IAM Policy (Least Privilege)

Attach this policy to the IAM user whose credentials are stored in
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration"
      ],
      "Resource": "arn:aws:lambda:*:*:function:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "states:DescribeStateMachine",
        "states:ListStateMachines",
        "states:CreateStateMachine",
        "states:UpdateStateMachine"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": [
        "<LAMBDA_EXECUTION_ROLE_ARN>",
        "<AWS_STEP_FUNCTIONS_ROLE_ARN>"
      ]
    }
  ]
}
```

Replace `<LAMBDA_EXECUTION_ROLE_ARN>` and `<AWS_STEP_FUNCTIONS_ROLE_ARN>` with
the actual ARN values.

---

## Lambda Execution Role Policy

This is the role passed as `--role` when creating Lambda functions
(`LAMBDA_EXECUTION_ROLE_ARN`). It needs read access to the **specific** secret.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "<SERVICE_SECRET_ARN>"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

---

## Deployment Flow

1. **Validate ASL** — check that `orchestration/order-creation-state-machine.asl.json` is valid JSON.
2. **Package** — `scripts/package_lambdas.py` zips `src/` into `build/<name>.zip` for each deployable Lambda.
3. **Deploy Lambdas** — for each function (`validate_order`, `resolve_delivery_address`, `create_order_step`):
   - If the function exists → `update-function-code`.
   - Otherwise → `create-function` (runtime `python3.12`, timeout 30s, memory 256 MB).
   - Set `SERVICE_SECRET_ARN` environment variable (ARN only; the secret value is fetched at runtime).
4. **Render ASL** — resolve real Lambda ARNs and substitute them into the ASL placeholder ARNs via `jq`.
5. **Deploy State Machine** — create or update the Step Functions state machine with the rendered definition.
6. **Summary** — write a deployment summary table to the GitHub Actions run summary.

---

## Local Development

When `SERVICE_SECRET_ARN` is **not set**, `get_service_secret()` returns an empty
dict and all configuration falls back to plain environment variables. No changes
needed for local dev — just set `DATABASE_URL` (or `DB_HOST`/`DB_USER`/`DB_PASS`/`DB_NAME`)
in your `.env` / shell as before (e.g. `DATABASE_URL` or `DB_HOST`/`DB_USER`/`DB_PASS`/`DB_NAME`).
