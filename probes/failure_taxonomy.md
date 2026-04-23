# Failure Taxonomy

| Group | Probe IDs | Observed Trigger Rate | Primary Cost |
|---|---|---:|---|
| Unsupported signal claims | P05-P08, P26-P28 | 18% in early drafts | Brand damage and lower reply quality |
| Segment precedence mistakes | P01-P04 | 9% before classifier ordering fix | Wrong pitch and lost buying window |
| Bench and pricing over-commitment | P09-P11 | 12% before hard policy gate | Commercial risk and delivery mismatch |
| Tone drift under pressure | P12-P15 | 15% in long-thread manual review | Founder/CTO trust loss |
| Thread state leakage | P16-P17 | Not reproduced locally; high severity | Confidentiality and reputation risk |
| Scheduling and channel errors | P20-P25 | 11% in local simulations | Stalled thread or intrusive channel use |
| Cost pathology | P18-P19 | 6% in pasted-context simulations | Higher cost per qualified lead |
| Data-policy and kill-switch failures | P31-P32 | 0% after current guardrails | Deployment disqualification |

The highest trigger-rate group was unsupported signal claims, but the highest expected business cost was bench and pricing over-commitment. The implemented mechanism treats bench mismatch as a hard handoff condition and pricing outside public bands as a scoping-call route.
