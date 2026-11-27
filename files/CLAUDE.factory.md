## Delegation
Sonnet builds, Haiku swarms, Opus reviews. Delegate every repo search to the `search`
or `grep` subagent, every test run to the `test` subagent, and diff reviews to the
`audit` subagent, passing it the output of `git diff` (all Haiku 5.5). When lookups
are independent, launch those subagents in parallel in one message. Keep only their
summaries in the main context.

## Advisor (Opus 5.5)
Call the advisor at exactly these moments, and not for routine work:
- before a plan locks (after orientation, before the first edit);
- when the same error shows up a second time;
- before calling the task done: first get the `audit` result on the final diff,
  then call the advisor so Opus signs off on that synthesized diff.
- If the advisor raises a problem at sign-off: fix it, re-run `audit` on the new diff,
  then call the advisor once more. At most 2 sign-off rounds; if it still objects,
  stop and report the open issue to the user instead of looping.

## Factory principles (adapted from Lauren Tan's pstack)
Plan
- State acceptance criteria before the first edit, and name the data shape (types,
  structures) before writing logic.
- Split work into small units that each end in a check; verify one before the next.
- Prefer the smallest change; delete dead weight before adding. Build a script or
  codemod instead of repeating an edit by hand.
Bugs
- Reproduce first, on the same surface, before fixing. Ask "why" until the root
  cause; fix that, not the symptom (use superpowers:systematic-debugging).
- After two failed fixes that share a premise, question the premise (this is also
  the "same error twice" advisor moment).
Verify
- Prove it works on the real artifact: run the tests, the command, or the UI.
  "It compiles" or "types pass" is not proof. Test behavior with literal expected
  values, not implementation details.
- Give `audit` the task goal and acceptance criteria along with `git diff`.
- You own every subagent's result: read what it changed and summarize it yourself.
Evidence
- Every claim carries its evidence or a label in the same sentence: measured,
  inferred, or guess. For research, cite the source and say plainly what is
  unverified (see the research-playbook skill).
Learn
- When the same correction comes up a second time, encode it as a check (lint rule,
  test, hook, or script) in the project instead of adding more instructions.
  Propose the check; add a CLAUDE.md line only if no check is possible.
Autonomy
- Proceed on reversible work and present the result. Always pause before
  hard-to-reverse actions: force-push, deploys, deleting data, messages to people.
- A guard hook enforces this for Bash commands. When it asks or denies, that is
  intentional: do not rephrase, split or obfuscate the command to get around it.
  Tell the user what you wanted to run and why, and let them decide.
- One task per session. Final reply: what changed, how it was verified, what is left.

## Fast decisions
Two forks reach Decider automatically through hooks: retry-or-stop after a failed
command (follow a sharp note unless the error clearly says otherwise), and
inline-vs-delegate after five lookups in a row (hand the rest to the named subagent
unless the next lookup finishes the job).
For another genuine toss-up between a few options (e.g. which of several candidate
files to edit), you may run
`~/.claude/bin/decide "<question>" "<opt>=<what it means>" ... <<< "<minimal context>"`
and use its `choice` when `confidence` >= 0.8. Send only the context the decision
needs: never secrets, keys, or whole files.

## Agent monitor
Only when the user asks to watch or open the agent monitor: run
`~/.claude/bin/agent-monitor` and open http://localhost:8790 in the browser pane.
Stop it with `~/.claude/bin/agent-monitor stop` when the user is done.
