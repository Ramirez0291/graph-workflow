# PRD — <product name>

- **Owner:** <the CEO>
- **Version:** <date>

## Problem
<who has what problem today, and what it costs them. Two or three sentences.>

## Users
- <primary user>: <what they are trying to do>
- <secondary user, if any>

## The main user task
<the one thing a user must be able to do for this product to exist. Punk tests this first.>

## Success criteria
| # | Criterion (observable) | How we will know |
|---|---|---|
| S1 | | |

## Edge cases
Main sweeps every requirement against each category and writes a row for each case that reads two ways; the CEO fills Decision. Column order is fixed, because `gw gate 1` reads it. A category with nothing in dispute goes on the "No dispute" line instead of getting rows.

| # | Req | Category | Case | Options | Recommended | Decision | Source |
|---|---|---|---|---|---|---|---|
| E1 | S1 | threshold | <the case> | <A / B> | <Main's pick> | <the CEO writes this> | CEO |

- No dispute: <categories, comma separated>

| Category | Ask |
|---|---|
| threshold | exactly at, just under, too little left |
| interleave | another action arrives mid-state: does the count carry on |
| repeat | the same action twice fast, two sources at once |
| time-cross | a window crosses another deadline |
| counting | what counts as one, what does not |
| environment | reload, midnight, several tabs or windows, background throttling |
| failure | a step fails halfway, stored data is corrupt |

> Source is `CEO`, or `Main provisional` for a row found after Gate 1; `gw gate 3` waits until the CEO confirms it.

## Scope — in
- ...

## Scope — out (non-goals)
- ... <be specific; vagueness here becomes rework>

## Constraints
- <platform, data, compliance, budget, deadline>

## Planning notes
- <what existing code already does, feasibility limits, reuse decisions; one line each. This replaces separate feasibility or assessment files.>

## Open questions
- ...
