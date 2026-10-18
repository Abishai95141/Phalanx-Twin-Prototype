# Phalanx Twin prototype

A working daily decision loop — Readiness → Decisions → Decision / Why → Workbench → Twin → Epoch → Provenance —
over a live simulated fleet of 8 aircraft, on the existing screen design, built in one day with four the build agents
sessions.

| Document | Contents |
|---|---|
| [DEMO.md](DEMO.md) | the demo walk-through on the live LinuxONE server: clicks, what is real behind each screen, what is honest to say |
| [DEVELOPMENT.md](DEVELOPMENT.md) | the development document: product spec (requirements), system spec (architecture, data, twin state, engines, triage, policies, decision cycle, orders, event log, API, screens), tech stack, phases with the stack per phase, expected results, test plan, risks, session briefs |

It runs end to end on IBM LinuxONE — see [`../ibmz/README.md`](../ibmz/README.md). The planned full system is in [`../architecture/`](../architecture/README.md); the data it reads is described in
[`../data-layer/`](../data-layer/README.md); the consumer rules in [`../../RULES.md`](../../RULES.md) apply.
