# Target Failure Mode

## Selected Failure

`P10`: false staffing commitment when a prospect asks for a team that includes at least one stack with zero visible Tenacious bench capacity.

Why this specific failure:

- It is directly tied to Tenacious's core product promise: bench-backed delivery capacity.
- It converts an LLM mistake into an operational commitment, not just a weak email.
- The remediation cost is low because the fix is a narrow policy gate plus human handoff, not a broad model rewrite.

## Business-Cost Derivation

Source numbers used:

- Talent-outsourcing ACV floor: `$240,000`
- Discovery-call-to-proposal conversion range: `35%–50%`
- Proposal-to-close conversion range: `25%–40%`
- Stalled qualified-thread baseline: `30%–40%`
- Brand-event proxy cost used elsewhere in repo: `$500` per visibly bad outreach event

These values come from the challenge brief and the memo's published Tenacious math.

### Conservative Per-Incident Cost

For `P10`, the conservative assumption is not that every bad promise loses a deal. The assumption is:

- One false staffing commitment contaminates one otherwise qualified outsourcing opportunity.
- Probability that the contaminated opportunity is lost: `25%`
- Value of the at-risk opportunity: `ACV floor = $240,000`

Arithmetic:

`expected cost per P10 incident = 0.25 x $240,000 = $60,000`

### Exposure Per 100 Qualified Staffing Conversations

Observed trigger rate for `P10` in the probe library: `21%`

Arithmetic:

`100 conversations x 21% trigger rate x $60,000 expected loss per incident`

`= 100 x 0.21 x $60,000`

`= $1,260,000 expected exposed value per 100 qualified staffing conversations`

This is the ROI reason to attack it first: one narrow guardrail protects six-figure expected value very quickly.

## Alternatives Considered

### Alternative 1: `P13` offshore-perception tone failure

Failure:

- A defensive or cliché-heavy reply to a prospect who says they do not want an offshore body shop.

Why it matters:

- Real brand risk with senior engineering buyers.

Cost model:

- Observed trigger rate: `33%`
- Conservative brand-event cost proxy from the memo: `$500` per bad outreach event

Arithmetic:

`100 conversations x 33% x $500 = $16,500 expected exposure`

Why it loses to `P10`:

- The trigger rate is higher, but the per-incident downside is far lower than a false delivery commitment attached to a qualified outsourcing opportunity.

### Alternative 2: `P23` dual-control booking stall after explicit meeting intent

Failure:

- The prospect says they want a slot, but the system adds friction instead of moving into booking.

Why it matters:

- It recreates the exact stalled-thread problem Tenacious wants to remove.

Cost model:

- Observed trigger rate: `21%`
- Conservative expected value of one qualified conversation at the ACV floor:

`35% discovery-to-proposal x 25% proposal-to-close x $240,000`

`= 0.35 x 0.25 x $240,000`

`= $21,000 expected value per qualified conversation`

Exposure arithmetic:

`100 qualified conversations x 21% trigger rate x $21,000`

`= 100 x 0.21 x $21,000`

`= $441,000 expected exposed value per 100 qualified conversations`

Why it loses to `P10`:

- It is still important, but the conservative expected-value exposure is about one-third of `P10`.
- The business can recover some stalled threads with human follow-up; a false staffing promise is harder to unwind cleanly once said.

### Alternative 3: `P30` false-positive AI-maturity signal from loud marketing

Failure:

- The system mistakes AI-flavored marketing language for operational AI maturity and pitches too aggressively.

Cost model:

- Observed trigger rate: `35%`
- Brand-event proxy cost: `$500`

Arithmetic:

`100 conversations x 35% x $500 = $17,500 expected exposure`

Why it loses to `P10`:

- High frequency, but still much smaller expected dollar downside than one false delivery commitment against a qualified outsourcing deal.

## Selection Rationale

`P10` wins on ROI because it combines three favorable conditions:

1. The downside is tied to Tenacious's highest-value motion: talent outsourcing at `$240,000+` ACV.
2. The fix is local and cheap: a visible bench-capacity gate and a mandatory human handoff when any required stack is at zero.
3. The business harm is harder to recover from than the alternatives. Tone failures and scheduling stalls can sometimes be repaired; a false staffing commitment can damage trust with both the buyer and the Tenacious delivery lead in one move.

## Mechanism Chosen

- Load bench visibility from `seed/bench_summary.json`.
- Infer required stacks from the brief.
- Attach `bench_match` to every hiring signal brief.
- If any required stack has zero visible capacity, set `needs_human=true`.
- Route staffing and pricing specifics to a human rather than letting the model improvise commitment language.

This is why the repo treats bench mismatch as the first hard commercial guardrail, even though other categories have slightly higher aggregate trigger rates.
