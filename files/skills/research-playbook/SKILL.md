---
name: research-playbook
description: Step-by-step playbook for research questions and ML experiments - literature or docs lookups, comparing methods, running and reporting experiments. Use when a task asks "what is known about X", "which approach is better", "does this result hold", or when writing up findings, so every claim ends up sourced, labeled (measured / inferred / guess) and checked against counterexamples.
---

# Research playbook

Copy these steps into the task list before starting, then work them in order.

1. **Frame the question.** Write the exact question and what a good answer must
   contain (the decision it informs, the metric, the scope). If the question is
   vague, narrow it before searching.

2. **Find primary sources.** Prefer papers, official docs, datasets and code over
   blog posts or summaries. Use the `deep-research` skill for broad lookups. Record
   each source's link and date; note when a source is secondhand.

3. **Log claims with evidence.** For every claim you plan to use, keep a line:
   claim, source (or command/experiment), label: **measured** (you or the source
   observed it), **inferred** (follows from measured facts), or **guess**.

4. **Experiments (if any).** Before running: state the hypothesis, the baseline and
   the metric. Fix and record seeds, data split, versions and config. Run more than
   once when variance matters and report mean with spread, not one number. Log runs
   (`weights-and-biases` or `mlflow` skills) so results are reproducible.

5. **Look for counterexamples.** Search for results that contradict your answer,
   and check your experiment for leakage, wrong baselines or cherry-picked runs.
   Change the conclusion if the evidence says so.

6. **Check citations.** Verify that each cited paper exists and says what you
   claim (`nature-ref-verifier` skill for reference lists).

7. **Report.** Lead with the answer. Then: evidence per claim with its label and
   source; what is unverified or uncertain; limits of the experiment; what would
   change the conclusion. Never present an inferred or guessed point as measured.
