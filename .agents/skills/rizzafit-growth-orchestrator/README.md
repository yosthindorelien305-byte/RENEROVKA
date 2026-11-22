# RizzaFit Growth Orchestrator — Antigravity Skill

This package contains one project-specific Antigravity Agent Skill.

## Install in the RizzaFit workspace

Copy the folder `rizzafit-growth-orchestrator` into:

`.agents/skills/`

The resulting path must be:

`.agents/skills/rizzafit-growth-orchestrator/SKILL.md`

Antigravity's global alternative is `~/.gemini/config/skills/`, but this skill is intended for the RizzaFit workspace.

## Run it

Open the RizzaFit repository in Antigravity and invoke:

`/rizzafit-growth-orchestrator`

Suggested first prompt:

> Выполни полный план из скилла RizzaFit Growth Orchestrator. Работай автономно над безопасными локальными изменениями, пройди этапы по порядку, сохрани отчёт и подготовь изменения к моей проверке. Ничего не выкатывай на production, не меняй Search Console и не трогай пользовательские данные.

## Safety

The skill explicitly prohibits production deployment, live payment actions, real-user messaging, destructive database operations, and unapproved merges. It allows safe local inspection, implementation, testing, and a reviewable report.
