# Brief N — <task title>

One page. The only channel into the Coder and the Tester: say what and how it is checked, not how it is built.

## Goal
<one or two sentences: what exists when this is done, from the user's point of view>

## Serves
- PRD success criterion S<k>: "<quote it>"

## Acceptance criteria
| # | Criterion (observable behavior) |
|---|---|
| A1 | |

## Edge cases
Rows from the PRD this task touches, decision copied verbatim (`gw brief` compares). Each needs a test naming its id. Write "none" if the task touches none.

| # | Case | Decision |
|---|---|---|
| E1 | | |

## Interface
What a test calls and what it observes. No internal helpers or algorithms unless a test calls them.
- <signature / command and flags / endpoint and payload / file format>

For an orchestration task, replace the list with two tables.

| Event (input) | Data |
|---|---|
| FullscreenEntered | screen id |
| Tick | now (ms) |

| Effect (output) | Data |
|---|---|
| HidePet | — |

## Risk layer
<domain | orchestration | native | UI> — <why the change is most likely to break here>

## Files
- May change: <paths, comma separated>
- May create: <paths>
- Must not touch: <paths>

## Constraints
- <conventions from architecture.md that apply>
- Non-negotiables touched: <none | which; each is also an acceptance criterion>

## Test command
`<exact command>`

## Tests
- Visible: <paths> (filled by Main after the spec check)
- Manual check for the risk layer, if no test reaches it: <steps → expected result>
- More tests you have not seen will run against the same criteria.

## Change notes
- <date> A2 reworded: <why>

## Loop notes
- Loop 1: <what failed, as behavior; never test code>
