# Enterprise control plane

VERITY improves capable enterprise models by controlling the work around them, rather than
pretending a prompt or small local distill raises their underlying reasoning capability.

## Execution contract

1. **Deterministic preflight.** Retrieve user-provided sources, prior context, installed tools,
   system constraints, and expected evidence before planning begins.
2. **Risk-aware routing.** Use deterministic or local actions for low-risk work. Escalate only
   difficult planning, ambiguity resolution, or cross-component review to an explicitly selected
   enterprise model.
3. **Role separation.** Planner, executor, read-only verifier, and seam reviewer are distinct
   roles. The executor does not certify its own result.
4. **Evidence ledger.** Each material claim needs a receipt: source retrieval, command/test result,
   rendered artifact, or independent observation.
5. **Fail closed.** A missing schema, evidence receipt, verifier result, budget permission, or
   external-action authorization is not a pass.
6. **Regression evaluation.** Test actual failure modes: stale assumptions, missing tool discovery,
   invented checks, unsafe external actions, and incomplete handoffs. Valid JSON alone is not a
   quality measure.

## Cost, privacy, and authority

Enterprise calls are opt-in and should have an explicit model, budget, and privacy scope. The
enterprise model may propose or review; deterministic policy gates and independent task-matched
tests remain the authority for completion.

## Local-model policy

Small local models can be useful for bounded classification, constraint extraction, and candidate
tool discovery. They are not trusted autonomous planners or acceptance authorities unless they
demonstrate sustained task-matched performance under the same gates used in production.
