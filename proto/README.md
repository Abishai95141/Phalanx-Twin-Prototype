# proto/ — Phalanx Twin prototype

The build of [`docs/prototype/DEVELOPMENT.md`](../docs/prototype/DEVELOPMENT.md). Rules in
[`../RULES.md`](../RULES.md) apply to every file here.

| Folder | Side | What |
|---|---|---|
| `runner/` | fleet | the simulated fleet: 8 preview tail worlds stepped day by day (imports the data layer, read-only) |
| `ground/` | ours | gate, as-of store, twin, engines, triage, policies, loop, event log, API — never imports `phalanx` |
| `web/` | ours | the screens (copied from `video/screens/`; the film copies stay untouched) |
| `eval/` | evaluation | may read truth of training worlds and the overlay; nothing in `ground/` imports it |
| `tests/` | — | golden, rule, boundary and integration tests |
| `runs/` | — | generated run directories (git-ignored) |

## Environments

Two `uv` environments, Python 3.12:

```bash
cd proto/runner && uv venv --python 3.12 .venv && uv pip sync requirements.lock.txt --python .venv/bin/python
```

```bash
cd proto/ground && uv venv --python 3.12 .venv && uv pip sync requirements.lock.txt --python .venv/bin/python
```

- `runner/requirements.lock.txt` = the data layer's exact pins (`requirements.datalayer.lock.txt`, exported from
  its `uv.lock`) + FastAPI and uvicorn. Always run runner code through `runner/run.sh`: it puts the data-layer
  source on `PYTHONPATH` and stops Python and numba from writing caches into it.
- `ground/requirements.lock.txt` is compiled from `ground/requirements.in`; it must never contain the data layer.

## Phase 0 go/no-go

```bash
proto/runner/run.sh proto/runner/gonogo.py
```

Builds the 8 worlds to 2026-06-22 06:00 IST, publishes the history to `runs/gonogo/fleet/`, steps one day with
the station routine only, publishes the delta, and checks history and delta against the preview row for row,
the ingest window of every delta file, the contract hash of every file and the step time. Report:
`runs/gonogo/gonogo_report.json`.

## Services

`proto/deploy/launch.json` has `runner` (port 8710) and `ground` (port 8700). Runner API: `POST /init`,
`POST /step`, `GET /status` (see `runner/service.py`).

## The LinuxONE server (where everything runs)

IBM Z (s390x, big-endian), Ubuntu 24.04, user `linux1`. See DEVELOPMENT.md §3 for what changed on IBM Z.

```bash
proto/deploy/sync.sh                      # push code and docs (never deletes server files)
```

```bash
proto/deploy/remote.sh 'proto/runner/run.sh proto/runner/gonogo.py'   # run anything there
```

```bash
proto/deploy/tunnel.sh                    # screens and API at http://localhost:8701
```

- `proto/deploy/ssh_config`: host `phx` (IPv4) and `phx6` (the same server via NAT64, for IPv6-only networks);
  the scripts pick whichever answers.
- On the server: conda env `~/envs/phx` (`$PHX_PY`), repo `~/phalanx/Phalanx-Solution`, data layer
  `~/phalanx/phalanx_data_layer_preview` (+ `data/v0.9/fleet_ipc`, the preview as Arrow IPC);
  `proto/deploy/server.env` sets the paths, `PHX_NUMBA_SHIM=1` and `PHX_STORE_FORMAT=arrow`.
- At most 2 heavy worker processes on the server (3 vCPU, 7.8 GB RAM).

### Public HTTPS

nginx serves the app at https://148.100.99.205/ and http://148.100.99.205/ (`proto/deploy/nginx-phalanx.conf` →
`/etc/nginx/sites-available/phalanx`, shared block `nginx-phalanx-app.conf` → `/etc/nginx/snippets/phalanx-app.conf`).
Browsers now try HTTPS first, so port 443 must stay open (iptables rules for 80 and 443, saved with
`sudo netfilter-persistent save`). The certificate is a Let's Encrypt **IP-address certificate** (short-lived
profile, about 6 days), issued by acme.sh as `linux1` over HTTP-01 (webroot `/var/www/acme`) and copied to
`/etc/nginx/ssl/`; acme.sh's cron renews it and reloads nginx. To reissue it by hand:

```bash
proto/deploy/remote.sh '~/.acme.sh/acme.sh --renew -d 148.100.99.205 --ecc --force'
```

## Run directory

```
runs/<run_id>/
  fleet/<topic>/date=…/tail_no=…/part-<min_ingest>-<digest>.arrow     # consumer tree (Arrow IPC), contract 0.2.0
  _restricted_labels/fleet/labels.truth/…                             # truth: evaluation only, never ground/
```
