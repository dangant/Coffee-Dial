# Coffee Dial

## Trigger phrases

**`Review ideas`** — when the user sends this phrase on its own, invoke the `review-ideas`
skill (`.claude/skills/review-ideas/SKILL.md`). It reads the open enhancement ideas from
the deployed app, reads each one back to confirm the ask, and plans all of them.

Read back first, plan second, and stop at the plan — the user reviews and approves an idea
before any of it gets implemented.
