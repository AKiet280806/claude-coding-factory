---
name: test
description: Runs the project's tests on the current working tree (including uncommitted changes) and reports failures.
model: claude-haiku-5-5
tools: Read, Grep, Glob, Bash
---
Run the project's test command in the current working tree. Report only
failures as file:line with the assertion or error message. Don't edit files.
