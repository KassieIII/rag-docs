# Security policy

## Supported versions

Only the latest release on `main` is supported. There is no LTS branch.

| Version  | Supported          |
| -------- | ------------------ |
| 0.1.x    | :white_check_mark: |
| < 0.1.0  | :x:                |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security problems.

Email **honormorethangold@gmail.com** with:

- a short description of the issue,
- steps to reproduce or a proof-of-concept,
- the affected version / commit hash.

You should receive an acknowledgement within 72 hours. If the report is
confirmed, a fix will be released as a patch version and credited in the
changelog (unless you ask to stay anonymous).

## Scope

In scope:

- the `app/` Python package and its public HTTP surface,
- the Docker build and container runtime configuration,
- Alembic migrations.

Out of scope:

- vulnerabilities in upstream dependencies (please report those
  upstream); this project will track them via Dependabot,
- attacks that require a prior local-machine compromise,
- denial of service via expensive but legitimate inputs (this is a
  local-first demo and is not hardened for hostile public exposure).
