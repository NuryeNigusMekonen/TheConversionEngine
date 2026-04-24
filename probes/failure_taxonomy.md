# Failure Taxonomy

Canonical source: [adversarial_probe_library.json](./adversarial_probe_library.json)

Aggregation rule: each category's `aggregate trigger rate` is the arithmetic mean of the `observed_trigger_rate` values for the probes assigned to that category in the canonical JSON library.

## Coverage Audit

- Total probes in canonical library: `38`
- Unique probe IDs present in taxonomy: `38`
- Orphan probes: `0`
- Duplicate assignments: `0`
- Double-counted probes: `0`

Every probe from the library appears exactly once in the taxonomy below.

| Category | Shared Failure Pattern | Probe IDs | Count | Aggregate Trigger Rate |
|---|---|---|---:|---:|
| ICP misclassification | The system picks the wrong Tenacious segment or refuses to abstain when public evidence is too weak to support a tailored pitch. | `P01, P02, P03, P04` | 4 | 25.0% |
| hiring-signal over-claiming | The workflow turns thin public evidence into stronger hiring or restructuring claims than the brief can support. | `P05, P06, P07, P08` | 4 | 28.5% |
| bench over-commitment | The agent implies Tenacious can staff, overlap, or price an engagement beyond what the visible bench and approved commercial rules allow. | `P09, P10, P11, P12` | 4 | 21.7% |
| tone drift from style guide | Replies drift away from the Tenacious voice by becoming defensive, verbose, guilt-tripping, or condescending toward technical buyers. | `P13, P14, P15, P16` | 4 | 25.0% |
| multi-thread leakage | Context or channel eligibility leaks across two contacts at the same company, breaking thread isolation and confidentiality. | `P17, P18, P19` | 3 | 17.3% |
| cost pathology | The system spends too much model budget on long pasted context, repeated low-information follow-ups, or over-detailed analysis in-thread. | `P20, P21, P22` | 3 | 24.3% |
| dual-control coordination | A clear buyer intent signal arrives, but the system adds unnecessary friction or contradictory next steps instead of coordinating the handoff cleanly. | `P23, P24, P25` | 3 | 18.0% |
| scheduling edge cases across EU, US, and East Africa | Timezone ambiguity, regional overlap, and channel-confirmation mistakes cause avoidable booking confusion across the three operating regions. | `P26, P27, P28, P29` | 4 | 20.7% |
| signal reliability with false-positive notes | Public signals are loud but misleading, and the system mistakes marketing, generic tech leadership, or sparse peers for stronger evidence than they really are. | `P30, P31, P32, P33, P34` | 5 | 26.4% |
| gap over-claiming | The competitor-gap brief treats public legibility differences as proof the prospect lacks capability, strategy, or maturity. | `P35, P36, P37, P38` | 4 | 24.5% |

## Notes

- The taxonomy uses the exact category names from the challenge rubric and the canonical probe JSON.
- Aggregate trigger rates are descriptive rollups for prioritization, not a claim that all probes have equal business cost.
- The highest aggregate trigger-rate category is `hiring-signal over-claiming` at `28.5%`, but the target failure mode selected for ROI work is a more severe bench-commitment failure because its per-incident downside is larger in Tenacious economics.
