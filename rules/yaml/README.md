# Sentinel Analytics Rule YAML Wrappers

The four KQL detection rules in `rules/*.kql` are packaged here as Microsoft Sentinel Analytics Rule YAML files, matching the format used in the Azure-Sentinel GitHub repository's `Detections/` and `Solutions/*/Analytic Rules/` folders.

| File | Wraps |
|------|-------|
| `rule_01_poisoned_tool_description.yaml` | `../rule_01_poisoned_tool_description.kql` |
| `rule_02_cross_tool_reference.yaml` | `../rule_02_cross_tool_reference.kql` |
| `rule_03_tool_description_hash_drift.yaml` | `../rule_03_tool_description_hash_drift.kql` |
| `rule_04_original_recipient_tell.yaml` | `../rule_04_original_recipient_tell.kql` |

Each YAML file includes the KQL query inline (byte-identical to the canonical `.kql` file), MITRE ATT&CK mappings in `tactics` and `relevantTechniques`, OWASP Agentic Top 10 and MITRE ATLAS references in `tags`, watchlist dependencies declared in the description, incident configuration with custom-detail grouping, and alert detail overrides for analyst-friendly alert titles.

Deployment: import each YAML via the Sentinel UI (Analytics → Create → Import from template) or via the Sentinel Repositories CI/CD feature pointing to this folder.

The `.kql` files in `rules/` are the source of truth for detection logic; the YAML files here are deployment wrappers around that logic.
