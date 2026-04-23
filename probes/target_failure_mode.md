# Target Failure Mode

Target: bench and pricing over-commitment.

Why this is the highest-ROI failure to attack: Tenacious sells delivery capacity, not only software. A wrong signal in a cold email can damage reply rate, but a false capacity or pricing commitment can create a delivery promise the company cannot meet. Using the challenge ACV ranges, one mishandled qualified opportunity can affect a $240K-$720K outsourcing engagement or an $80K-$300K project consulting engagement.

Mechanism:

- Load `seed/bench_summary.json` into the enrichment layer.
- Infer required stacks from job titles, sector, and AI maturity signal.
- Attach a `bench_match` object to every hiring signal brief.
- Set `needs_human=true` when any required stack has zero visible capacity.
- Route pricing questions to public bands plus a discovery call; never invent a total contract value.

Business-cost derivation: if one false staffing commitment causes even a 10% probability of losing a $240K qualified outsourcing opportunity, expected cost is $24K. That dwarfs the incremental LLM and email cost of a conservative handoff.
