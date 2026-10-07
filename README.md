# Daily Financial Health Brief — starter

Build a reusable Skill that prepares a source-traceable financial brief for human review.

## Start

1. Read the [formal assignment](https://private-pecorino-70e.notion.site/Project-A-Daily-Financial-Health-and-Budget-Brief-Learner-assignment-3da0b700541e8137ab79f8cb26d1a827?source=copy_link) for the work and acceptance requirements.
2. Create your own repository from [this starter](https://github.com/GitRollTraining/financial-health-brief) using **Fork**, then clone your copy and work there.

## Supplied files

| File | Purpose |
|---|---|
| `README.md` | Starting instructions and links. |

Create the Skill, implementation and outputs described in the formal assignment. This starter supplies no business workflow implementation.

## Before you work

**Interview rule.** You conduct the stakeholder interview yourself, and the questions are yours. Do not connect a coding agent or any other AI to the interview to run, script, or automate it. The interview transcript is assessed together with the code; a project whose interview was run by an agent is not scored.

- Export your interview as the original Work Sim Markdown, save one final complete file per session under `interviews/`, and commit and push it with your code. Do not rewrite the export. If the export is unavailable, contact the facilitator.

- Use an Agent Skills-capable coding environment. Choose and document your implementation runtime and dependencies; no runtime or install command is supplied here.
- Follow the [shared course guide for session capture](https://classroom.google.com/c/ODcyMjA4NTkwNDk2/m/ODc0NzI2NzQzMzQ2/details) and verify capture is active before implementation. Keep credentials out of the repository.
- Meet the [stakeholder](https://work-sim.catalyte.ai/s/interview-r62mbg) to understand the work and relevant business sources. Read those online sources through their intended access route; an unavailable source is not permission to substitute repository data.

## Implemented skill

Read [daily-financial-health-brief/SKILL.md](daily-financial-health-brief/SKILL.md)
to run the read-only workflow. The [runtime instructions](daily-financial-health-brief/references/runtime.md)
include the complete live-source command, Python 3.9+/curl dependencies, access
contract and failure behavior. [Operating rules](daily-financial-health-brief/references/operating-rules.md)
document source meanings and calculations; [validation](daily-financial-health-brief/references/validation.md)
describes the regression suite. Required outputs are under `deliverables/`.

The original complete interview export is preserved under `interviews/`.
Current capture uses Entire 0.11.3 checkpoint refs under `refs/entire/checkpoints/`,
which differ from the course guide's `entire/checkpoints/v1` branch; capture
configuration and existing history have been preserved. Financial reports remain
drafts for operations-owner review.
