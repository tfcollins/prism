# Edit Run Tags via Web UI — Design Spec

**Date:** 2026-06-10
**Status:** Approved for planning
**Author:** Travis F. Collins (with Claude Code)

## Summary

Run tags (`key`→`value` pairs on a `TestRun`) can currently only be set at upload
time — there is no way to fix or add them afterward. This feature adds the ability
to **add**, **edit the value of**, and **delete** tags on an existing run through the
Run Detail page in the web UI, backed by three new REST endpoints. Because the matrix
dashboard and the tag-filter UI read tags live, editing a tag (e.g. `hw`,
`platform`, `boot_file`) retroactively updates those views on the next refresh —
making this the primary mechanism for correcting/back-filling the coverage wall.

## Goals

- Add a new `key=value` tag to an existing run.
- Edit the value of an existing tag.
- Delete a tag.
- Do all of the above from the existing Tags section on the Run Detail page.
- Record every change in the audit log.

## Non-goals

- No rename-key-in-place operation (a rename is delete + add, two user actions).
- No bulk/multi-run tag editing (Run Detail page, one run at a time).
- No full-tag-set "replace everything" editor.
- No new permission tier — any authenticated user may edit tags (matches the
  existing precedent that any logged-in user can already mutate runs).
- No tag-value normalization (no auto-lowercasing) — exact values matter for matrix
  grouping.

## Decisions (resolved during brainstorming)

| Topic | Decision |
| --- | --- |
| Operations | Add, edit value, delete (rename = delete + add) |
| Location | Run Detail page only (the existing Tags section) |
| Permissions | Any authenticated user + CSRF (matches run upload / set-calibration) |
| API shape | Granular REST subresource endpoints under the run |
| Audit | Yes — `run.tag.add` / `run.tag.update` / `run.tag.delete` |
| UI pattern | Inline editing (no modal), mirroring `CalibrationControl` |
| Normalization | None; trim whitespace and require non-empty only |

## Architecture

The feature slots into the existing router → repo → model layering. No schema/model
changes (the `run_tags` table already exists). No worker changes. The matrix and
tag-filter views require no changes — they read `RunTag` live.

```text
RunDetailPage (Tags section, inline edit)
  │  POST   /api/v1/runs/{id}/tags
  │  PUT    /api/v1/runs/{id}/tags/{key}
  │  DELETE /api/v1/runs/{id}/tags/{key}
  ▼
routers/runs.py ──► repos/runs.py (get_tag/create_tag/update_tag/delete_tag)
  │                                 └─► run_tags table (existing)
  └─► repos/audit.py (AuditRepo.record)
```

## Data model

No changes. Existing `RunTag` (`models/run.py`):
- Composite PK `(run_id, key)`; `key` `String(100)`; `value` `String(500)`, not null;
  index `ix_run_tags_kv` on `(key, value)`.

## API

All three endpoints live in `apps/api/src/prism_api/routers/runs.py`, are gated by
`current_user` + `csrf_protect`, and first load the run (404 if it does not exist).

### Add a tag

```
POST /api/v1/runs/{run_id}/tags
body: { "key": "<str>", "value": "<str>" }
```
- If a tag with `key` already exists on the run → **409** (`"tag already exists; use PUT to change it"`).
- Else create it → **201**, body `RunTagOut{key, value}`.

### Update a tag value

```
PUT /api/v1/runs/{run_id}/tags/{key}
body: { "value": "<str>" }
```
- If the tag does not exist → **404**.
- Else set the new value → **200**, body `RunTagOut{key, value}`.

### Delete a tag

```
DELETE /api/v1/runs/{run_id}/tags/{key}
```
- If the tag does not exist → **404**.
- Else delete → **204** (no body).

### Schemas (`schemas/run.py`)

- Reuse existing `RunTagOut { key: str, value: str }` for responses.
- Add `RunTagCreate { key: str, value: str }` — both `min_length=1`,
  `key` `max_length=100`, `value` `max_length=500`; values are trimmed (strip) and
  rejected if empty after trim.
- Add `RunTagUpdate { value: str }` — `min_length=1`, `max_length=500`, trimmed.

### Repo methods (`repos/runs.py`)

The existing `add_tag` is an upsert (`session.merge`) and is kept as-is for the
upload path. Add explicit, intention-revealing methods:

- `get_tag(run_id, key) -> RunTag | None`
- `create_tag(run_id, key, value) -> RunTag` (caller checks `get_tag` first; flushes)
- `update_tag(run_id, key, value) -> RunTag` (mutates existing row's value)
- `delete_tag(run_id, key) -> bool` (returns whether a row was removed)

### Audit

Via the existing `AuditRepo.record()`, one event per successful operation, with
`target_type="run"`, `target_id=run_id`, actor = current user:

- `run.tag.add` — detail `{ "key": <k>, "value": <v> }`
- `run.tag.update` — detail `{ "key": <k>, "old_value": <old>, "new_value": <new> }`
- `run.tag.delete` — detail `{ "key": <k>, "value": <v> }`

## Frontend

### Tags section on `RunDetailPage.tsx`

The existing read-only Tags badge list becomes editable inline (no modal; mirrors the
inline-mutation style of `CalibrationControl`):

- Each tag renders as `key = [value] [edit] [delete]`.
  - **Edit:** clicking edit replaces the value with a small Chakra `Input`
    (`maxLength=500`); **Save** issues the PUT, **Cancel** reverts.
  - **Delete:** a lightweight inline confirm (click again to confirm — the
    delete-project "type/confirm" pattern, not a modal), then DELETE.
- An **"Add tag"** row at the bottom: `key` input (`maxLength=100`) + `value` input
  (`maxLength=500`) + **Add** button → POST.
- Buttons show `loading` during their mutation; errors surface inline (e.g. red text
  "Tag already exists — edit it instead." on 409, "Tag no longer exists." on 404).

### react-query hooks (`api/queries.ts`)

Mirroring `useSetCalibration`:

- `useAddRunTag(runId)` → POST `/runs/{id}/tags`
- `useUpdateRunTag(runId)` → PUT `/runs/{id}/tags/{key}`
- `useDeleteRunTag(runId)` → DELETE `/runs/{id}/tags/{key}`

On success each invalidates:
- `['runs', 'detail', runId]` (refresh the run's tags),
- the project tag-filter queries (`['tag-keys', slug]`, `['tag-values', …]`),
- the matrix queries (`['matrix', …]`),

so the DUT/filter UI and the matrix wall reflect the change without a manual reload.

## Validation & edge cases

- **Empty key/value:** trimmed; empty after trim → 422 (pydantic) / blocked in UI.
- **Length:** key ≤ 100, value ≤ 500 (pydantic `max_length` + input `maxLength`).
- **No normalization:** values stored exactly as entered (case preserved) — matrix
  grouping depends on exact values, and fixing case is a valid edit.
- **No reserved keys:** editing `hw`/`platform`/`boot_file` is the intended use.
- **Add duplicate key →** 409, surfaced inline as "edit it instead."
- **Edit/delete a vanished tag (concurrent change) →** 404; UI shows the message and
  the list refetches.
- **Unknown run →** 404 from the run lookup.

## Testing

### Backend (`pytest`)

- Add: 201 + tag persisted + `RunTagOut` body.
- Add duplicate key: 409.
- Update: 200 + value changed.
- Update missing key: 404.
- Delete: 204 + tag gone.
- Delete missing key: 404.
- Unknown run id: 404 (add/update/delete).
- Auth required: 401 without session/bearer.
- CSRF required: 403 on POST/PUT/DELETE without the CSRF header.
- Validation: empty key, empty value, over-length key/value → 422.
- Audit: a `run.tag.add` / `run.tag.update` / `run.tag.delete` event is recorded
  with the expected `detail` (including `old_value`/`new_value` for update).

### Frontend (`vitest`)

- Tags section renders existing tags with edit + delete affordances.
- Add row calls `useAddRunTag` with `{key, value}`.
- Edit swaps the value to an input and Save calls `useUpdateRunTag`.
- Delete confirm calls `useDeleteRunTag`.
- 409/404 error text renders.
(Hooks mocked per the existing page-test pattern.)

### E2E (`playwright`)

- On a seeded run: add a tag, edit its value, delete it; assert the badge list
  updates after each; axe a11y clean.

## Open questions / future work

- Bulk tag editing across selected runs from the runs table (back-filling many runs
  at once) — deferred; would need a bulk endpoint + multi-select UI.
- Rename-key-in-place as a single operation — deferred (currently delete + add).
