# MetaVision - Second Brain

HackInnovision 2026, Track B: Agentic Workflow Automation & Context Engineering.

**Goal:** turn a sponsor commitment change into an evidence-backed impact plan, obtain human approval, update dependent event records, and verify the outcome even when a tool fails.

## Start here

- [Detailed Project B blueprint](temp/PROJECT_B_BLUEPRINT.md): requirements, architecture, stack, memory, agents, reliability, implementation sequence, evaluation, and demo strategy.
- [Official problem statement](HackInnovision2026_PS.pdf): the source of the event requirements.

## Repository status

Planning and repository initialization only. No application, dependency environment, or integrations have been implemented yet. Features in the blueprint are proposed work, not existing functionality.

Recommended first build: Python, LangGraph, SQLite, Pydantic, and Streamlit, with simulated email, tracker, document, and calendar tools. Add a live model after the deterministic workflow works.

## First implementation milestone

Build one vertical slice: synthetic sponsor email -> structured change -> dependency impact -> approval -> idempotent updates -> read-back verification -> audit trail. Include a deliberate tool failure and prove that replay does not duplicate effects.

## Event timing

The brief specifies November 14, 2026, midnight to noon. The timetable places submission and shortlisting at 9:30-10:00 AM, although the rules specify a noon deadline. Target a submission-ready build by 9:30 AM and confirm the operational cutoff with organizers. Times are interpreted as local event time (IST); the PDF does not state a timezone.

## Working conventions

- Keep secrets in local environment variables or an ignored `.env`; never commit credentials or real attendee/sponsor data.
- Keep synthetic fixtures separate from runtime state. Generated databases and temporary PDF renders are ignored.
- Keep `temp/PROJECT_B_BLUEPRINT.md` tracked: the folder name does not make this document disposable.
- Commit small, working increments. Document simulated connectors and known limits honestly.
- Install and lock application dependencies when implementation starts; this planning commit does not claim a runnable setup.
