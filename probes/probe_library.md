# Probe Library

Canonical structured artifact: [adversarial_probe_library.json](./adversarial_probe_library.json)

This Markdown file is the human-readable index for the probe corpus. The JSON file above is the source of truth for rubric evaluation because every entry there includes the required structured fields:

- `probe_id`
- `category`
- `setup`
- `expected_failure_signature`
- `observed_trigger_rate`
- `business_cost_framing`

The structured library currently contains `38` probes and covers all ten challenge categories:

| Category | Count |
|---|---:|
| ICP misclassification | 4 |
| hiring-signal over-claiming | 4 |
| bench over-commitment | 4 |
| tone drift from style guide | 4 |
| multi-thread leakage | 3 |
| cost pathology | 3 |
| dual-control coordination | 3 |
| scheduling edge cases across EU, US, and East Africa | 4 |
| signal reliability with false-positive notes | 5 |
| gap over-claiming | 4 |

Tenacious-specific probes are intentionally overrepresented. Examples include:

- `P09` and `P10`: bench-to-brief mismatch and over-promising scarce talent capacity
- `P13`: offshore-perception language from an in-house hiring manager
- `P19` and `P28`: warm-lead SMS gating after prior email reply
- `P35` and `P38`: competitor-gap phrasing that could patronize a self-aware CTO

Each structured entry is written to be conceptually reproducible from the entry alone. In addition to the required rubric fields, the JSON library also includes:

- `reproduction_notes` for how to rerun the scenario
- `tenacious_specificity` for why the failure matters in this outsourcing workflow
- `false_positive_note` where signal-reliability probes need an explicit caveat
