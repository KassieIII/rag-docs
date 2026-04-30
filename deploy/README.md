# Deploying rag-docs on a small VPS

This is a self-contained recipe to put rag-docs on a public domain
behind HTTPS, with the write endpoints protected by basic auth, on as
little as 4 GB RAM.

## What you need

- A Linux VPS with at least **4 GB RAM**, **2 vCPUs**, **20 GB disk**.
  Hetzner CX22 (€4.51 / month at the time of writing) is enough.
- A domain you control, with an `A` record pointing at the VPS IP.
- 5 minutes of uninterrupted attention.

## What you get

- `https://your-domain/health` &mdash; public, returns
  `{db, embedder, llm}` booleans.
- `https://your-domain/documents` &mdash; public read of the corpus.
- `https://your-domain/ask` &mdash; public; expensive (~30 s on CPU
  with `llama3.2:1b`), so consider rate-limiting upstream.
- `https://your-domain/ingest` &mdash; protected by basic auth so
  random callers don't fill your DB.
- Automatic Let's Encrypt certificate, auto-renewed by Caddy.

The api, db, and ollama containers are **not** exposed to the host.
Only Caddy listens on `:80` and `:443`.

## Step by step

```bash
# 1. on your laptop
ssh root@your-vps

# 2. on the server: clone and set up
git clone https://github.com/KassieIII/rag-docs.git
cd rag-docs/deploy
cp .env.example .env
nano .env       # fill DOMAIN, ACME_EMAIL, secrets, basic auth hash

# 3. generate a bcrypt hash for the basic auth password
docker run --rm caddy:2-alpine caddy hash-password --plaintext 'your-password'
# paste the result into INGEST_BASIC_AUTH in .env

# 4. run the deploy script (idempotent)
sudo bash deploy.sh
```

After the first run, follow-up changes are just:

```bash
git pull
sudo bash deploy.sh
```

## Memory budget at rest

| component        |   RAM (idle)  |
|------------------|:-------------:|
| postgres         |    ~80 MB     |
| ollama (1b model loaded) | ~1.3 GB |
| api + embedder   |    ~600 MB    |
| caddy            |    ~20 MB     |
| **total**        |   **~2 GB**   |

Leaves ~2 GB headroom for the LLM under load and the OS page cache.
The cross-encoder reranker adds ~200 MB if you turn it on.

## What is *not* covered here

- **Backups.** `pgdata` is just a docker volume. For a real deployment,
  schedule `pg_dump` to S3-compatible storage.
- **Observability.** No Prometheus exporter, no logs aggregation. For
  a $5 VPS demo this is fine; for a production tenant you'd add at
  least healthchecks scraped by an external monitor.
- **Authentication for `/ask`.** Currently public. If your eval set is
  not what you'd want to expose to the world, put `/ask` under the
  same basic auth block in the Caddyfile.

## Tearing it down

```bash
docker compose --env-file .env -f compose.prod.yml down -v
```

The `-v` removes volumes, including the corpus and the LLM weights.
Drop it if you want to keep them.
