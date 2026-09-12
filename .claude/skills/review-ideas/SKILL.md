---
name: review-ideas
description: Triggered by the bare phrase "Review ideas" (also /review-ideas). Reads the open enhancement ideas the user entered in Coffee Dial, repeats each one back to confirm the ask is understood, then writes an implementation plan for every open idea. Stops at the plan — never implements.
---

# Review ideas

The user types **`Review ideas`** and expects, in this order: their open ideas read back to
them, then a plan for each. Assume no other context — this fires in fresh chats.

## 1. Fetch

```
python .claude/skills/review-ideas/fetch_ideas.py --out <your scratchpad dir>
```

Prints JSON: `source`, `open_count`, `done_count`, `screenshots_saved`, `screenshot_dir`,
and `ideas` (open only, newest first).

Ideas live in the deployed app's Postgres, not local `coffee.db`. No credentials are
needed — the script reads the production API directly and needs no setup.

- If `open_count` is 0, say so, mention `done_count`, and stop.
- If it exits with setup instructions, the deployed host has moved. Relay them verbatim
  and **stop**; don't guess a URL or work around it.

## 2. Look at the screenshots

Any idea with a `screenshots` array has images already downloaded — **open every
`local_path` with the Read tool before writing anything about that idea.** They were
attached precisely because the idea is easier to show than to describe, so an idea
reviewed without looking at its picture is reviewed blind. A `screenshot_dir` is emptied
and refilled on each run, so what's there is current.

If a screenshot carries an `error` instead of a `local_path`, say so rather than guessing
at what it showed.

## 3. Read back — before any planning

For **each** open idea, in the order returned:

- Its title and details, quoted as entered.
- **The ask, in your own words** — what you understand they want built, concretely.
- Anything genuinely ambiguous about it, stated as the assumption you intend to make.

This step exists so the user can correct you before effort is spent. Do not merge it into
the plan, and do not skip it because an idea looks self-explanatory.

## 4. Research

Only now, look at the actual code each idea touches. This is a FastAPI + SQLAlchemy +
Jinja2 app: models in `app/models/`, business logic in `app/services/`, JSON endpoints in
`app/routers/api_*.py`, HTML routes in `app/routers/pages.py`, templates in
`app/templates/`. Prefer extending what exists over adding parallel machinery, and name
the real functions you intend to reuse. Note that there are no auto-migrations — new
tables go through `Base.metadata.create_all()` in `app/main.py` and column additions
through inline `ALTER TABLE` there.

## 5. Split by `needs_review`

Each idea carries a `needs_review` flag. It decides your authority over that idea, and the
two groups are handled differently in the same pass.

**`needs_review: true` — plan only.** The default, and how every idea used to be treated.

**`needs_review: false` — implement it.** The user has explicitly granted this: build it,
test it, commit it, and push to `main`, then report what shipped. No approval round trip.

Treat a missing flag as `true`. Never infer the grant from an idea looking small.

### The comprehension gate

Auto-implement means "no round trip when the path is clear" — not "build on a guess". Even
with the flag off, **stop and report instead of building** when:

- The idea is ambiguous enough that two readings would produce different work.
- Doing it needs a decision that is the user's to make, not a default you can pick.
- It touches something you should not do unreviewed: deleting or rewriting existing data,
  a destructive migration, auth, secrets, or anything affecting production records.

Say plainly which ideas you stopped on and what you'd need to proceed. An idea held back
for a good reason is a better outcome than a confident wrong build.

## 6. Plan the gated ones

If any open idea has `needs_review: true`, call `EnterPlanMode` and write **one plan file
covering those ideas**, a section per idea, each with:

- What it changes and why (tie it back to the idea as the user wrote it).
- The specific files to modify, and existing functions to reuse.
- How to verify it end to end, including tests where the behavior is testable
  (`python -m pytest -q`).

If the ideas interact — shared model, same page, one blocked on another — say so and
recommend an order. End the turn with `ExitPlanMode`.

For gated ideas, write no application code and do not commit: the user reviews and approves
those before they are implemented.

## 7. Tick off what you shipped

Mark an idea done once you have actually shipped and verified it:

```
PUT /api/v1/ideas/<id>   {"is_done": true}
```

against the same host `fetch_ideas.py` reported as `source`. The app stamps `completed_at`
itself and moves the row into Done, so the user doesn't have to revisit the page to close
out work they can already see landed.

**Only what you completed.** A gated idea you planned, an idea held at the comprehension
gate, and anything you shipped partially all stay open. Ticking those destroys the signal
the user relies on to know what still needs them — the cost of leaving one open too long is
an extra glance; the cost of closing one early is work that silently disappears.

Never tick an idea you did not implement in this pass.

## 8. Report

Close with what happened to each open idea: shipped (with the commit) and ticked off,
planned and awaiting approval, or held back with the reason.
