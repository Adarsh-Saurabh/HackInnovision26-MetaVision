# MetaVision - Second Brain

HackInnovision 2026, Track B: Agentic Workflow Automation & Context Engineering.

**Goal:** turn a sponsor commitment change into an evidence-backed impact plan, obtain human approval, update dependent event records, and verify the outcome even when a tool fails.

## Start here

- [Shared PC and skill setup](setup.md): consistent environment, Git workflow, Ponytail/Caveman installation and usage for every teammate.
- [Detailed Project B blueprint](temp/PROJECT_B_BLUEPRINT.md): requirements, architecture, stack, memory, agents, reliability, implementation sequence, evaluation, and demo strategy.
- [Complete system flowcharts](temp/PROJECT_B_SYSTEM_FLOWCHART.md): revision 2 visual workflow covering all six agents, mid-stream deliverables, corrections, scoped approval, adaptive replanning, recovery, outputs, and evaluation.
- [Official problem statement](HackInnovision2026_PS.pdf): the source of the event requirements.

## Repository status

Planning and repository initialization only. No application, dependency environment, or integrations have been implemented yet. Features in the blueprint are proposed work, not existing functionality.

Recommended first build: Python, LangGraph, SQLite, Pydantic, and Streamlit, with simulated email, tracker, document, and calendar tools. Add a live model after the deterministic workflow works.

Prototype scope: fabricate the cross-application dataset; defer Gmail, Sheets, and Calendar APIs. The blueprint adapts typed graph context and deterministic-rule patterns from the supplied uplan-ai analysis, while retaining source evidence and adding independent preflight checks, approvals, and verified execution. Prior application code is not included.

## First implementation milestone

Build one vertical slice: synthetic email thread and team chat -> structured change -> dependency impact and deliverable classification -> preflight -> scoped approval -> idempotent updates -> read-back verification -> action ledger and agent timeline. Include a fail-once tracker write and a concurrent deliverable edit that triggers plan v2, delta re-approval, and reuse of completed effects. Prove that replay does not duplicate effects.

## Event timing

The brief specifies November 14, 2026, midnight to noon. The timetable places submission and shortlisting at 9:30-10:00 AM, although the rules specify a noon deadline. Target a submission-ready build by 9:30 AM and confirm the operational cutoff with organizers. Times are interpreted as local event time (IST); the PDF does not state a timezone.

## Working conventions

- Keep secrets in local environment variables or an ignored `.env`; never commit credentials or real attendee/sponsor data.
- Keep synthetic fixtures separate from runtime state. Generated databases and temporary PDF renders are ignored.
- Keep `temp/PROJECT_B_BLUEPRINT.md` tracked: the folder name does not make this document disposable.
- Commit small, working increments. Document simulated connectors and known limits honestly.
- Install and lock application dependencies when implementation starts; this planning commit does not claim a runnable setup.
