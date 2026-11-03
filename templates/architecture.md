# Architecture — <product name>

The index, two pages at most. Component detail lives in `architecture/<component>.md` and is read only when a brief names it.

## Overview
<two or three sentences: the main pieces and how data flows>

## Components
| Component | Responsibility | Location | Detail file |
|---|---|---|---|

## Contracts
| Interface | Between | Source of truth |
|---|---|---|

## Layers and how each is tested
| Layer | Where | Tested by |
|---|---|---|
| domain | | unit tests |
| orchestration | core: <path> · shell: <path> | unit tests on the core with event sequences; shell by Punk and the CEO |
| native / OS | | <manual check / integration test> |
| UI | | Punk screenshots |

## Orchestration rule
Logic with flags, timers or races lives in a pure `step(state, event) -> (state, effects)` core, with time as an event. Shell files translate and execute but never import the state type; `gw.json` lists them in `shell_paths` and the forbidden imports in `shell_forbid`.

## Registry files
Main-only; Coders request entries in their handoff. Listed in `gw.json` → `registry_files`.
- <src/lib.rs, src/main.ts, router table, package.json, Cargo.toml>

## Shared resources
Tests take ports from `GW_PORT_BASE`, temp files from `GW_TMP`, and never share a database file. `gw` runs one test suite at a time.
- <port range, database, cache>

## Conventions
| Topic | Rule |
|---|---|
| Language / versions | |
| Layout | |
| Errors and logging | |
| Dependencies | Main approves; added only in a skeleton or registry commit |

## Test
| Item | Value |
|---|---|
| Test command | `<runs the full suite>` (also in gw.json) |
| Test folder | <path> |
| Worktree setup | `<npm ci --prefer-offline / pnpm install (shared store) / shared CARGO_TARGET_DIR / uv sync>`; never copy dependencies or build output. Links into the main checkout work, and `gw close` removes them before deleting the worktree |
| Build outputs | git-ignored, or `gw check` counts them as changes |

## Non-negotiables
Trust boundaries where someone can cause the failure on purpose. The audit may simplify these, never delete them; a brief that touches one states it as an acceptance criterion.
- Auth and permissions: <...>
- Untrusted input: <never reaches SQL, a shell, a path or HTML unescaped>
- Secrets: <never in code, logs, URLs or error messages>

## Demo (for Punk)
| Item | Value |
|---|---|
| Start | `<command>`; ready when <...> |
| Screenshot | `<e.g. npx playwright screenshot --full-page --viewport-size="1280,800" <url> 01-home.png>` |
| Screen sizes | <desktop / phone / both> |
| No screen | <how a user drives it> |
