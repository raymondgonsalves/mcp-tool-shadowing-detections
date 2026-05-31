# MCP Tool Shadowing Detection Pack — Recruiter Brief

A 3-minute overview of what was built and why it matters. For the full technical detail, see [`README.md`](README.md).

---

## What this project is

A set of four detection rules for Microsoft Sentinel that catch a Model Context Protocol (MCP) attack class called **Tool Shadowing** — built, tested against real attack data captured in a lab, and documented end-to-end.

Tool Shadowing targets AI agents connected to multiple MCP servers simultaneously. An attacker who controls one server can embed instructions in that server's tool description that hijack other trusted, high-privilege tools the agent uses. There is no protocol-level defense available today; detection on the protocol logs the AI host already produces is the layer organizations can deploy now.

---

## Why this matters

AI agents that connect to external systems through MCP are moving into production workflows fast. The protocol was designed for composability — letting agents combine tools from many sources — not for adversarial scenarios where one of those sources is malicious.

The threat model behind this project (the third project in my portfolio arc) demonstrated the attack in a controlled lab: a malicious calendar tool's description instructed the AI to redirect outgoing emails to an attacker-controlled address. Some AI models caught the attempt; others complied silently. The protocol delivered the malicious instructions every time. There is no architectural fix available today.

That is exactly the kind of gap a Security Operations Center (SOC) team gets asked to address: when the upstream defense isn't there yet, what detections can the SOC deploy now? This project is the operational answer to that question.

---

## What I built

- **Four KQL detection rules** for Microsoft Sentinel that catch Tool Shadowing using protocol logs the MCP host already generates
- **A Python ingestion pipeline** that normalizes raw MCP protocol logs and sends them to a Microsoft Sentinel custom log table, authenticated via Azure Entra ID
- **Two Sentinel watchlists** that carry reference data and approved-baseline tracking, including inline disclosures of lab constraints surfaced in every alert
- **A traceability document** mapping each detection rule back to a specific finding from the prior threat model report, the OWASP and MITRE framework alignments, and the lab evidence demonstrating the rule fires
- **A forensic evidence baseline** — captured logs cryptographically hashed before any detection rule was tested against them, proving the rules verify against real attack output rather than against something the pipeline shaped

---

## What it demonstrates

- **Detection engineering for Microsoft Sentinel** — KQL authoring, watchlist design, custom log table schema, Data Collection Rule deployment via infrastructure-as-code (this project aligns directly with the Microsoft SC-200 Security Operations Analyst certification)
- **Cloud security architecture** — Azure resource design, OAuth-based service authentication, secure ingestion through the Logs Ingestion API
- **Detection-as-code discipline** — rules version-controlled in git with substantive headers documenting classification, mappings, limitations, and analyst triage steps
- **Scope and trade-off judgment** — two originally-planned rules dropped during the project for documented data-availability reasons, with the reasoning preserved in the project log rather than hidden
- **Threat-research-to-operations translation** — turning a written threat model into deployable detection content, an underrepresented skill in most security portfolios

The frameworks the work aligns to: OWASP Agentic Top 10, MITRE ATT&CK, MITRE ATLAS. The technical stack: Microsoft Sentinel, Microsoft Defender XDR, Azure, Python, KQL.

---

## How it fits in the broader portfolio

This is the fourth project in a four-project arc on AI agent security:

| Phase | Project | Focus |
|-------|---------|-------|
| Use | [Mastering SOC Agentic AI](https://modern-character-425.notion.site/Ray-Gonsalves-2394b1f7c9ba8043a797f55386422214) | Using AI agents in production SOC workflows |
| Defend | [Defending Agentic AI](https://github.com/raymondgonsalves/Defending_Agentic_AI) | Policy-gated AI agent triage with human approval gates |
| Analyze | [Tool Shadowing Threat Model](https://modern-character-425.notion.site/Tool-Shadowing-Attack-MCP-Connected-AI-Agent-3584b1f7c9ba804483d1e1aa5fb148f6) | Written threat model report on the attack class |
| **Detect** | **MCP Detection Pack (this project)** | **Operational detection rules for the attack** |

Each project uses the format that fits its work: videos for hands-on demonstrations, a written report for threat analysis, code-and-video for detection engineering. Together they show the full lifecycle: how to use these systems, how to defend them, how to analyze new attacks against them, and how to detect those attacks in operational telemetry.

---

## Architecture at a glance

![Architecture Diagram](docs/figures/figure_00_architecture.png)

*The detection pipeline. The left panel shows the lab environment where AI agents and the test MCP servers run. The right panel shows the Azure cloud infrastructure where logs are ingested, stored, and queried by detection rules in Microsoft Sentinel. Authentication uses OAuth (dashed lines); data transfer uses HTTPS POST (solid lines).*

---

## Where to look

- [`README.md`](README.md) — full technical overview including the architectural reasoning, the four-rule defense-in-depth coverage matrix, deployment instructions, and the demo flow
- [`docs/TRACEABILITY_MATRIX.md`](docs/TRACEABILITY_MATRIX.md) — cross-cutting document mapping each rule to its threat model finding, framework alignment, and lab evidence
- [`rules/`](rules/) — the four KQL detection rules, each with a substantive header
- [`docs/figures/`](docs/figures/) — captured evidence from the lab, including each rule firing on real attack data and the forensic integrity baseline of the source logs

A video walkthrough is in production and will be linked here when published.

---

## Contact

Ray Gonsalves
[LinkedIn](https://www.linkedin.com/in/raymond-gonsalves) | [Portfolio on Notion](https://modern-character-425.notion.site/Ray-Gonsalves-2394b1f7c9ba8043a797f55386422214)
