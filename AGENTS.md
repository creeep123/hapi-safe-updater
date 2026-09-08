# Project rules

## Sources of truth

1. `docs/management/CONTROL_PANEL.md` defines project status and decisions.
2. `docs/specs/COMPANION_PATCHED_HUB_UPGRADE_SPEC.md` defines the mandatory production gate for a Hub carrying HAPI Companion.
3. `.scratch/companion-patched-hub-upgrade/ISSUE.md` tracks the executable rollout work.

## Hard boundaries

- This repository owns updater behavior. Never write updater implementation into the HAPI Companion repository.
- A production Hub with required local patches must use source mode and fail closed on a missing, changed, or conflicting patch.
- Candidate verification must finish before production files are mutated.
- Never print, copy into this repository, or persist HAPI/Companion credentials.
- Never claim a patched-Hub rollout is safe based only on `/health`; verify the complete configured contract and rollback target.
- Do not change the production Hub or its database while developing or testing this repository unless the user explicitly authorizes a rollout.
