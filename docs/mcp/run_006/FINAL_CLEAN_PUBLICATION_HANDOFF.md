# Run 006 final clean Develop handoff

Date: 2026-10-17. This is a **local isolated publication candidate**, not a remote update or Run 006 completion. No Abaqus, datacheck, real QueueRunner, commit, push, merge, or original-repository history rewrite was performed in this final cleanup.

## Exact Git state

| Ref | SHA | Result |
| --- | --- | --- |
| Original/public `Develop` (read-only `ls-remote` on 2026-10-17) | `b1e97ae7c1eba0dc047a3d1b51123725630283cf` | Still old; recheck immediately before any manual update. |
| Earlier audit-only clean `Develop` | `114c8118dfc7ed3712c59a4ef2cd9eeb0a8e30e8` | Private backup only; **not** the final publication tip. |
| **Final clean `Develop`** | **`339ba8fcdeb0e79151f385004b978b2d6c1e1fd4`** | Use this exact tip for the scoped manual history update. |
| `main` | `345faac8a4917c8aa0eb05921ff46d6bddc0e55d` | Unchanged. |

The final candidate was cloned from the earlier clean bundle and filtered **only** for `docs/mcp/run_006/PROCESS_LINEAGE_EVIDENCE.json` and `docs/mcp/run_006/GATE_B_RESULTS.md` on `Develop`. The earlier bundle had already removed `.audit_g2_4/`. The two evidence files were copied byte-for-byte into a separate private local backup before filtering; the original private `.audit_g2_4` copy (1,486 files) and complete old-history bundle remain intact. The final clone has just local `Develop` and `main` refs, no remote, no tags, no original/replace refs, and no old-history reflog. Isolated Git garbage collection removed the old prefilter tip object.

`git rev-list --all --objects -- <path>` returned zero for **each** of the three authorized paths. `git fsck --full --no-reflogs` passed. The filtered `Develop` tree has 103 non-target files; all 103 retain the earlier clean candidate's exact blob ID and mode. `main` retains its original SHA. These checks are about the candidate's **reachable Git history**, not GitHub caches, pull-request refs, forks, mirrors or other clones.

## Recovered current work

The final clone contains the last tested Run 006 development state as **uncommitted working-tree changes**: native process evidence/persistence, warning parser, Agent Command Console UI, Project/default-runtime isolation, README, MCP/Project docs and regression tests. A binary diff patch applied without conflicts after `git apply --check`. Sixteen modified tracked files matched the recovery preview byte-for-byte; nine selected new source/test/docs files were separately copied and hash-checked. No old `Develop` merge, old `.git`, raw process JSONL or real Project data was copied.

The final candidate can be opened independently in GitHub Desktop as a local repository. Its intentionally absent remote prevents an accidental push before the owner completes the scoped history update. The separate private recovery package includes `final_clean_history.bundle`, `run006_current_work.patch`, byte-verified copies of the two removed evidence files, and a 10-file selected-untracked snapshot; the earlier private backup retains `.audit_g2_4`. A second fresh clone from the new bundle successfully applied the patch and restored all selected files: **26 recovered files, zero hash mismatches** against the final candidate, with `git diff --check` passing. Keep the package and restore-check clone outside every public repository.

## Quality and publication scan

- Full non-Solver pytest, existing LangChainEnv Python: **226 passed, 1 skipped in 54.45 s**. The skip is the Agent Command Console Tk display test at `tests/test_agent_command_console_ui.py:63`; it is not counted as passed. The main-window Tk 1280x800/1440x900 layout test passed after test event-loop synchronization without weakening its width assertions.
- Focused MCP stdio/Agent/Project/process-evidence/parser/Tk suite: **82 passed, 2 skipped in 26.42 s**. Both skips are Agent Console display-availability checks. Native Abaqus end-to-end process evidence remains unverified.
- `git diff --check`, `git fsck`, local link checks for README (8 links) and MCP docs (4 links), and three-path reachable-history checks passed. No broken relative links were found in those checked files.
- No tracked `.db`, `.odb`, `.cae`, `.jsonl`, `queue.json`, `live_status.json` or `settings.json`; no such untracked fixture/output was included. Local real-run Retry reports, temporary Projects/runtimes, private backup directories and engineering outputs were deliberately excluded. Pattern scans found no credential-like token in the candidate.
- Some **non-target historical technical reports** still contain development-machine absolute paths, including one user-profile temporary-backup path. No credential or engineering result was found in the reviewed matches. Their publication/privacy acceptability remains an owner decision. They are outside the three authorized history-removal paths; this run did **not** broaden the rewrite.

Project data ownership changes are only in the recovered development worktree. New Project defaults are user-level/configurable and new-install No Project runtime is per-installation. A legacy source-tree runtime with existing data remains in place to avoid hiding/duplicating old jobs. Deliberately opening one formal Project from stable and development builds concurrently is still not guaranteed safe if the stable build does not honor the newer lock. No real Project was migrated or modified.

## Owner-controlled remote update

**Stop** if the live remote `Develop` differs from the expected old SHA, if `main` changes, if another branch/tag/ref carrying the targets appears, if branch protection rejects a scoped update, or if the privacy review above is unacceptable. Recheck the three-path history query and private backups first. The following is a **manual instruction, not an executed command**; run it only after separate authorization, from the final clean clone (or a verified copy), never the old development checkout:

```powershell
$repo = '<FINAL_CLEAN_CLONE>'
$url = 'https://github.com/BrunelXian/AbqJobPilot.git'
$old = 'b1e97ae7c1eba0dc047a3d1b51123725630283cf'
$new = '339ba8fcdeb0e79151f385004b978b2d6c1e1fd4'

git -C $repo rev-parse Develop
git -C $repo rev-parse main
git -C $repo rev-list --all --objects -- .audit_g2_4 docs/mcp/run_006/PROCESS_LINEAGE_EVIDENCE.json docs/mcp/run_006/GATE_B_RESULTS.md
git ls-remote --heads --tags $url
```

Only if the live `Develop` is **exactly** `$old`, `main` is unchanged, and the owner approves the remaining publication scope, the single-ref operation would be:

```powershell
git -C $repo push --force-with-lease=refs/heads/Develop:b1e97ae7c1eba0dc047a3d1b51123725630283cf $url 339ba8fcdeb0e79151f385004b978b2d6c1e1fd4:refs/heads/Develop
```

Do not run `--force`, `--mirror`, `--all`, or push from the old audit-bearing checkout. A lease failure means stop and reassess, not retry with broader force. This pushes **only the clean committed history tip**; it does not publish the uncommitted Run 006 code.

After the owner updates remote `Develop`, verify the live SHA and fresh-clone `git rev-list --all --objects --` results for all three targets. Then either configure the final clean local repository's GitHub remote in GitHub Desktop or clone the cleaned remote into a new directory and restore the private tracked patch plus **only** the selected new files. Review staged files, run tests and commit the recovered work through GitHub Desktop on top of clean `Develop`, followed by an ordinary push. Remove the old audit-bearing checkout from Desktop's repository list without deleting it; never merge/pull/push its old branch back into clean history. Retain the original checkout, old-history bundle, private evidence copies and clean-history recovery package until the owner verifies both the remote and the new daily-use checkout.

If remote history replacement misbehaves, stop publication and coordinate recovery from private backups in a new private checkout. Do not routinely restore the old audit-bearing ref to the public remote. Rewritten branch history does **not** guarantee removal from GitHub caches, pull requests, forks, mirrors or other clones; coordinate any further purge separately.

## Pending solver acceptance

Run 006 remains open. The preserved `FINAL_SANITY_REVIEW_PLAN.md` calls for one new disposable Project and one CPU=1/GPU=0 Job, datacheck plus full run, zero-warning terminal classification, native phase-specific Process Evidence, SQLite/report references, and persistence after reopening the Project. This run did **not** start Abaqus or create a new real test record.

**CLEAN_DEVELOP_CANDIDATE_READY** for owner review of the local three-path-clean history and recovered code. Remote update and Run 006 acceptance are separate, unperformed steps; the Agent Console display skip and residual non-target historical paths remain explicitly disclosed.
