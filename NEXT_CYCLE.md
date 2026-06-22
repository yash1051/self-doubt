# v3.1.5 (shipped) → v3.2.0 prompt (or convergence)

## What cycle 6 shipped
- `Guard(component_floors={"evidence_rate": 90, ...})` constructor
  param. Each component with a floor fires a `low_<component>` trigger
  (yellow) when its score drops below the floor.
- 2 new tests: per-component floor fires the right trigger; floor
  that's easy to clear doesn't fire.

## Convergence declaration — v3.1 score subsystem complete

Six cycles in, the v3.1.x series has shipped everything the score
subsystem can reasonably carry without new dependencies or design
decisions:

- v3.1.0: tests + CI + bug fixes
- v3.1.1: --on-goal default flipped to None (safety default fix)
- v3.1.2: strict mode + score() + on_goal tri-state
- v3.1.3: score_floor gate
- v3.1.4: diagnostic reason text + score_breakdown()
- v3.1.5: per-component floors

The remaining gaps are scope-expansion, not polish:
- Embedding-based similarity (requires deps, design decision)
- Runnable LangGraph demo (Tier 2 illustrative-only currently)
- External monitoring integration (out of v3 scope)

The loop has converged on the score subsystem. Future cycles
should either:
- Tackle the embedding-based similarity (Tier 1, but a real design
  decision about which embedding model to standardize on), OR
- Tackle the LangGraph demo (Tier 2 polish), OR
- Acknowledge convergence and let the loop rest.

## Hypothesis for cycle 7 (v3.2.0)

The single highest-leverage Tier 2 work remaining is a **runnable
LangGraph demo**. v3.0 docs show illustrative code in
`references/framework-integration.md`; v3.2 ships an example that
the CI can actually run, proving the framework integration isn't
fictional. This unblocks downstream users who want a real
reference impl.

**Specific tasks:**

1. Add `examples/langgraph_demo.py` that imports `guard.Guard` and
   wires it into a LangGraph-style state graph (even if LangGraph
   isn't installed — make it a self-contained simulator that follows
   the same pattern).
2. Update `references/framework-integration.md` to point at the
   new example.
3. Add `tests/test_langgraph_demo.py` that runs the demo and
   asserts the scorecard prints "✅ chain intact".

## Verification
- pytest 100% green
- demo still 85 → 5 sends
- new langgraph demo runs and produces a valid scorecard
- ≤ 5 files changed, ≤ 200 LOC net
