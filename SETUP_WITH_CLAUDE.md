# Set up with Claude Code

Open Claude Code inside this repository folder and paste the prompt below. Claude
will review the package, show you every change, and install only after you approve.

```text
Install the claude-coding-factory setup from this repository into my Claude Code config.

1. Read README.md, install.py and the files under files/ so you understand what will
   change. Tell me in a few lines what the setup does and anything that looks risky
   for my machine.
2. Check prerequisites: `claude --version` (needs 2.1.330+), python3, git. Stop and
   tell me if something is missing.
3. Run `python3 install.py --dry-run` and show me the full diff for settings.json and
   CLAUDE.md, plus the list of files it will add or update. Point out any existing
   hooks or settings of mine that the install touches. If I already set a different
   `model` or `advisorModel`, ask whether to keep it (`--keep-models`).
4. Wait for me to say "go". Then run `python3 install.py` (with `--keep-models` if I
   asked) and report the backup folder it printed.
5. Verify: run `~/.claude/bin/decide "Should this failed command be retried?" retry stop <<< "ETIMEDOUT"`.
   If it says no API key, tell me to paste my OpenRouter or Perplexity key into
   ~/.claude/decider.env myself (do not ask me to paste the key into the chat), then
   re-run the check after I confirm.
6. Tell me to start a new Claude Code session so the new CLAUDE.md rules load, and
   how to open the monitor (`~/.claude/bin/agent-monitor`, http://localhost:8790).
```

To remove it later, ask Claude to run `python3 uninstall.py --dry-run`, show you the
diff, and then run `python3 uninstall.py` after you approve.
