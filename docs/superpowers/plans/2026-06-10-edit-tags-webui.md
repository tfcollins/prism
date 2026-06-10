# Edit Run Tags via Web UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let any authenticated user add, edit the value of, and delete tags on an existing run from the Run Detail page, via three new REST endpoints, with each change audited.

**Architecture:** Three granular subresource endpoints (`POST/PUT/DELETE /api/v1/runs/{id}/tags[/{key}]`) added to the existing runs router, backed by new explicit `RunRepo` tag methods and the existing `AuditRepo`. The Run Detail page's read-only Tags section becomes an inline editor (extracted into a focused `TagsEditor` component) wired with three react-query mutation hooks. No model/migration changes — the `run_tags` table already exists, and the matrix/tag-filter views read tags live so edits reflect on refresh.

**Tech Stack:** FastAPI + SQLAlchemy (strict mypy), pytest. React 18 + Chakra UI v3 + react-query, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-06-10-edit-tags-webui-design.md`

**Conventions for every task:**
- Backend commands run from `apps/api/`; frontend from `apps/web/`.
- CI parity for backend lint: `uv run ruff check . && uv run ruff format --check . && uv run mypy src` (the CI `api` job runs the format check too — do not skip it). Frontend: `npm run lint && npm run build`.
- Single backend test: `uv run pytest tests/<file>::<test> -v`. Single frontend test: `npx vitest run <path>`.
- Commit at the end of each task with the message shown.

---

## File Structure

**Backend (`apps/api/src/prism_api/`):**
- `repos/runs.py` — add `get_tag`, `create_tag`, `update_tag`, `delete_tag` (keep existing `add_tag`).
- `schemas/run.py` — add `RunTagCreate`, `RunTagUpdate` (reuse existing `RunTagOut`).
- `routers/runs.py` — add `POST /{run_id}/tags`, `PUT /{run_id}/tags/{key}`, `DELETE /{run_id}/tags/{key}`.

**Backend tests:** `apps/api/tests/test_run_tags.py` (repo unit tests + router HTTP tests).

**Frontend (`apps/web/src/`):**
- `api/queries.ts` — add `useAddRunTag`, `useUpdateRunTag`, `useDeleteRunTag`.
- `components/TagsEditor.tsx` — the inline tag editor (add/edit/delete), used by RunDetailPage.
- `components/TagsEditor.test.tsx` — component test.
- `pages/RunDetailPage.tsx` — replace the read-only Tags badge list with `<TagsEditor runId={run.id} tags={run.tags} />`.

**Frontend e2e:** `apps/web/e2e/run-tags.spec.ts`.

---

## Task 1: Repo tag methods

**Files:**
- Modify: `apps/api/src/prism_api/repos/runs.py`
- Test: `apps/api/tests/test_run_tags.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_run_tags.py`:

```python
"""Run tag editing — repo methods + HTTP endpoints."""

from prism_api.models.project import Project
from prism_api.models.run import RunStatus, TestRun
from prism_api.repos.runs import RunRepo


def _run(db_session) -> TestRun:
    p = Project(slug="proj", name="Proj")
    db_session.add(p)
    db_session.flush()
    run = TestRun(project_id=p.id, name="r", status=RunStatus.PASS)
    db_session.add(run)
    db_session.flush()
    return run


def test_get_tag_missing_returns_none(db_session):
    run = _run(db_session)
    assert RunRepo(db_session).get_tag(run.id, "hw") is None


def test_create_then_get_tag(db_session):
    run = _run(db_session)
    repo = RunRepo(db_session)
    repo.create_tag(run.id, "hw", "ad9081")
    got = repo.get_tag(run.id, "hw")
    assert got is not None
    assert got.value == "ad9081"


def test_update_tag_changes_value(db_session):
    run = _run(db_session)
    repo = RunRepo(db_session)
    repo.create_tag(run.id, "hw", "ad9081")
    repo.update_tag(run.id, "hw", "adrv9009")
    assert repo.get_tag(run.id, "hw").value == "adrv9009"


def test_delete_tag_removes_and_reports(db_session):
    run = _run(db_session)
    repo = RunRepo(db_session)
    repo.create_tag(run.id, "hw", "ad9081")
    assert repo.delete_tag(run.id, "hw") is True
    assert repo.get_tag(run.id, "hw") is None
    assert repo.delete_tag(run.id, "hw") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_run_tags.py -v`
Expected: FAIL — `AttributeError: 'RunRepo' object has no attribute 'get_tag'`.

- [ ] **Step 3: Add the repo methods**

In `apps/api/src/prism_api/repos/runs.py`, add these methods to `RunRepo` (place them next to the existing `add_tag`/`tags_for` methods). Keep the existing `add_tag` unchanged. `RunTag` is already imported in this file.

```python
    def get_tag(self, run_id: str, key: str) -> RunTag | None:
        return self._session.get(RunTag, (run_id, key))

    def create_tag(self, run_id: str, key: str, value: str) -> RunTag:
        tag = RunTag(run_id=run_id, key=key, value=value)
        self._session.add(tag)
        self._session.flush()
        return tag

    def update_tag(self, run_id: str, key: str, value: str) -> RunTag | None:
        tag = self.get_tag(run_id, key)
        if tag is None:
            return None
        tag.value = value
        return tag

    def delete_tag(self, run_id: str, key: str) -> bool:
        tag = self.get_tag(run_id, key)
        if tag is None:
            return False
        self._session.delete(tag)
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_run_tags.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Lint**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/prism_api/repos/runs.py apps/api/tests/test_run_tags.py
git commit -m "feat(api): add RunRepo tag get/create/update/delete methods"
```

---

## Task 2: Tag endpoints + schemas + audit

**Files:**
- Modify: `apps/api/src/prism_api/schemas/run.py`
- Modify: `apps/api/src/prism_api/routers/runs.py`
- Test: `apps/api/tests/test_run_tags.py` (extend)

- [ ] **Step 1: Write the failing HTTP tests**

Append to `apps/api/tests/test_run_tags.py`:

```python
from prism_api.auth import hash_password
from prism_api.repos.audit import AuditRepo
from prism_api.repos.users import UserRepo


def _login(client, db_session):
    UserRepo(db_session).create(email="u@x.com", password_hash=hash_password("pw"))
    db_session.commit()
    r = client.post("/api/v1/auth/login", json={"email": "u@x.com", "password": "pw"})
    assert r.status_code == 200


def _seed_run(db_session) -> str:
    run = _run(db_session)
    db_session.commit()
    return run.id


def test_add_tag_requires_auth(client, db_session):
    rid = _seed_run(db_session)
    assert client.post(f"/api/v1/runs/{rid}/tags", json={"key": "hw", "value": "x"}).status_code == 401


def test_add_tag_requires_csrf(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    # logged in but no X-Prism-Csrf header
    r = client.post(f"/api/v1/runs/{rid}/tags", json={"key": "hw", "value": "x"})
    assert r.status_code == 403


def test_add_tag_creates(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    csrf = client.cookies.get("prism_csrf")
    r = client.post(f"/api/v1/runs/{rid}/tags", json={"key": "hw", "value": "ad9081"},
                    headers={"X-Prism-Csrf": csrf})
    assert r.status_code == 201
    assert r.json() == {"key": "hw", "value": "ad9081"}
    # persisted + audited
    assert RunRepo(db_session).get_tag(rid, "hw").value == "ad9081"
    events = [e.action for e in AuditRepo(db_session).list_for_project(
        db_session.get(TestRun, rid).project_id)]
    assert "run.tag.add" in events


def test_add_duplicate_key_conflicts(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    csrf = client.cookies.get("prism_csrf")
    h = {"X-Prism-Csrf": csrf}
    client.post(f"/api/v1/runs/{rid}/tags", json={"key": "hw", "value": "a"}, headers=h)
    r = client.post(f"/api/v1/runs/{rid}/tags", json={"key": "hw", "value": "b"}, headers=h)
    assert r.status_code == 409


def test_add_tag_unknown_run_404(client, db_session):
    _login(client, db_session)
    csrf = client.cookies.get("prism_csrf")
    r = client.post("/api/v1/runs/nope/tags", json={"key": "hw", "value": "a"},
                    headers={"X-Prism-Csrf": csrf})
    assert r.status_code == 404


def test_add_tag_validation(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    csrf = client.cookies.get("prism_csrf")
    h = {"X-Prism-Csrf": csrf}
    assert client.post(f"/api/v1/runs/{rid}/tags", json={"key": "", "value": "a"}, headers=h).status_code == 422
    assert client.post(f"/api/v1/runs/{rid}/tags", json={"key": "k", "value": "  "}, headers=h).status_code == 422
    assert client.post(f"/api/v1/runs/{rid}/tags", json={"key": "k" * 101, "value": "a"}, headers=h).status_code == 422


def test_update_tag(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    csrf = client.cookies.get("prism_csrf")
    h = {"X-Prism-Csrf": csrf}
    client.post(f"/api/v1/runs/{rid}/tags", json={"key": "hw", "value": "a"}, headers=h)
    r = client.put(f"/api/v1/runs/{rid}/tags/hw", json={"value": "b"}, headers=h)
    assert r.status_code == 200
    assert r.json() == {"key": "hw", "value": "b"}
    assert RunRepo(db_session).get_tag(rid, "hw").value == "b"
    events = [e.action for e in AuditRepo(db_session).list_for_project(
        db_session.get(TestRun, rid).project_id)]
    assert "run.tag.update" in events


def test_update_missing_tag_404(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    csrf = client.cookies.get("prism_csrf")
    r = client.put(f"/api/v1/runs/{rid}/tags/hw", json={"value": "b"},
                   headers={"X-Prism-Csrf": csrf})
    assert r.status_code == 404


def test_delete_tag(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    csrf = client.cookies.get("prism_csrf")
    h = {"X-Prism-Csrf": csrf}
    client.post(f"/api/v1/runs/{rid}/tags", json={"key": "hw", "value": "a"}, headers=h)
    r = client.delete(f"/api/v1/runs/{rid}/tags/hw", headers=h)
    assert r.status_code == 204
    assert RunRepo(db_session).get_tag(rid, "hw") is None
    events = [e.action for e in AuditRepo(db_session).list_for_project(
        db_session.get(TestRun, rid).project_id)]
    assert "run.tag.delete" in events


def test_delete_missing_tag_404(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    csrf = client.cookies.get("prism_csrf")
    r = client.delete(f"/api/v1/runs/{rid}/tags/hw", headers={"X-Prism-Csrf": csrf})
    assert r.status_code == 404
```

> Confirm `AuditRepo` exposes `list_for_project(project_id)` (it does — see `repos/audit.py`). If the accessor differs, query `AuditEvent` rows directly instead.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_run_tags.py -v`
Expected: the new HTTP tests FAIL (404 route not found / schema import error).

- [ ] **Step 3: Add the request schemas**

In `apps/api/src/prism_api/schemas/run.py`, add (near the existing `RunTagOut`). Use `Annotated` + `StringConstraints` so values are trimmed and length-bounded; an all-whitespace value fails `min_length` after stripping.

```python
from typing import Annotated

from pydantic import StringConstraints

TagKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
TagValue = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class RunTagCreate(BaseModel):
    key: TagKey
    value: TagValue


class RunTagUpdate(BaseModel):
    value: TagValue
```

> `BaseModel` is already imported in this file. If `from typing import Annotated` / the pydantic import already exist at the top, merge rather than duplicate.

- [ ] **Step 4: Add the endpoints**

In `apps/api/src/prism_api/routers/runs.py`, add the three endpoints (mirror the `set_calibration` handler's dependency style and audit usage). Ensure imports include `RunTagCreate`, `RunTagUpdate`, `RunTagOut` from `prism_api.schemas.run`, and that `AuditRepo`, `RunRepo`, `current_user`, `csrf_protect`, `session_dep`, `status`, `HTTPException` are imported (the calibration handler already uses all of these).

```python
@router.post("/{run_id}/tags", response_model=RunTagOut, status_code=status.HTTP_201_CREATED)
def add_run_tag(
    run_id: str,
    body: RunTagCreate,
    user: User = Depends(current_user),
    __: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
) -> RunTagOut:
    runs = RunRepo(session)
    run = runs.get_by_id(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    if runs.get_tag(run_id, body.key) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "tag already exists; use PUT to change it")
    tag = runs.create_tag(run_id, body.key, body.value)
    AuditRepo(session).record(
        user_id=user.id,
        action="run.tag.add",
        project_id=run.project_id,
        target_type="run",
        target_id=run_id,
        detail={"key": tag.key, "value": tag.value},
    )
    return RunTagOut(key=tag.key, value=tag.value)


@router.put("/{run_id}/tags/{key}", response_model=RunTagOut)
def update_run_tag(
    run_id: str,
    key: str,
    body: RunTagUpdate,
    user: User = Depends(current_user),
    __: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
) -> RunTagOut:
    runs = RunRepo(session)
    run = runs.get_by_id(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    existing = runs.get_tag(run_id, key)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tag not found")
    old_value = existing.value
    runs.update_tag(run_id, key, body.value)
    AuditRepo(session).record(
        user_id=user.id,
        action="run.tag.update",
        project_id=run.project_id,
        target_type="run",
        target_id=run_id,
        detail={"key": key, "old_value": old_value, "new_value": body.value},
    )
    return RunTagOut(key=key, value=body.value)


@router.delete("/{run_id}/tags/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run_tag(
    run_id: str,
    key: str,
    user: User = Depends(current_user),
    __: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
) -> None:
    runs = RunRepo(session)
    run = runs.get_by_id(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    existing = runs.get_tag(run_id, key)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tag not found")
    value = existing.value
    runs.delete_tag(run_id, key)
    AuditRepo(session).record(
        user_id=user.id,
        action="run.tag.delete",
        project_id=run.project_id,
        target_type="run",
        target_id=run_id,
        detail={"key": key, "value": value},
    )
```

> Note: `body.key`/`body.value` arrive already trimmed (StringConstraints `strip_whitespace`). The `{key}` path param on PUT/DELETE is matched against stored keys as-is.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_run_tags.py -v`
Expected: PASS (all repo + HTTP tests).

- [ ] **Step 6: Full suite + lint**

Run: `uv run pytest -q --no-cov && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
Expected: all pass, no lint/format/type errors.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/prism_api/schemas/run.py apps/api/src/prism_api/routers/runs.py apps/api/tests/test_run_tags.py
git commit -m "feat(api): add/update/delete run tag endpoints with audit"
```

---

## Task 3: react-query mutation hooks

**Files:**
- Modify: `apps/web/src/api/queries.ts`

- [ ] **Step 1: Read the existing patterns**

Read `apps/web/src/api/queries.ts` — note the `useSetCalibration` mutation (POST/PATCH via `api`, `useQueryClient`, `invalidateQueries`) and the existing `import type { ... } from './types'` line. Confirm a `RunTag` type (`{ key: string; value: string }`) is exported from `./types`; if it is not, add it there in this task.

- [ ] **Step 2: Add the hooks**

Append to `apps/web/src/api/queries.ts` (merge any new type import into the existing `import type ... from './types'` line):

```typescript
export function useAddRunTag(runId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (tag: { key: string; value: string }) =>
      (await api.post<RunTag>(`/runs/${runId}/tags`, tag)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['runs', 'detail', runId] });
      qc.invalidateQueries({ queryKey: ['projects'] });
      qc.invalidateQueries({ queryKey: ['matrix'] });
    },
  });
}

export function useUpdateRunTag(runId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ key, value }: { key: string; value: string }) =>
      (await api.put<RunTag>(`/runs/${runId}/tags/${encodeURIComponent(key)}`, { value })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['runs', 'detail', runId] });
      qc.invalidateQueries({ queryKey: ['projects'] });
      qc.invalidateQueries({ queryKey: ['matrix'] });
    },
  });
}

export function useDeleteRunTag(runId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (key: string) => {
      await api.delete(`/runs/${runId}/tags/${encodeURIComponent(key)}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['runs', 'detail', runId] });
      qc.invalidateQueries({ queryKey: ['projects'] });
      qc.invalidateQueries({ queryKey: ['matrix'] });
    },
  });
}
```

> The broad `['projects']` / `['matrix']` invalidations refresh the tag-filter UI and the matrix wall after an edit. They are key-prefix matches (react-query invalidates any query whose key starts with these), so no project slug is needed in the hook.

- [ ] **Step 3: Typecheck + lint**

Run: `npm run build && npm run lint`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/api/queries.ts apps/web/src/api/types.ts
git commit -m "feat(web): add run tag add/update/delete hooks"
```

---

## Task 4: `TagsEditor` component + wire into RunDetailPage

**Files:**
- Create: `apps/web/src/components/TagsEditor.tsx`
- Test: `apps/web/src/components/TagsEditor.test.tsx`
- Modify: `apps/web/src/pages/RunDetailPage.tsx`

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/TagsEditor.test.tsx`:

```typescript
import { ChakraProvider } from '@chakra-ui/react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { system } from '../theme';
import type { RunTag } from '../api/types';

const addMutate = vi.fn();
const updateMutate = vi.fn();
const deleteMutate = vi.fn();

vi.mock('../api/queries', () => ({
  useAddRunTag: () => ({ mutate: addMutate, isPending: false, isError: false }),
  useUpdateRunTag: () => ({ mutate: updateMutate, isPending: false, isError: false }),
  useDeleteRunTag: () => ({ mutate: deleteMutate, isPending: false, isError: false }),
}));

import { TagsEditor } from './TagsEditor';

const TAGS: RunTag[] = [{ key: 'hw', value: 'ad9081' }];

function renderEditor(tags: RunTag[] = TAGS) {
  return render(
    <ChakraProvider value={system}>
      <TagsEditor runId="r1" tags={tags} />
    </ChakraProvider>,
  );
}

describe('TagsEditor', () => {
  it('renders existing tags', () => {
    renderEditor();
    expect(screen.getByText('hw')).toBeInTheDocument();
    expect(screen.getByText('ad9081')).toBeInTheDocument();
  });

  it('adds a tag', () => {
    renderEditor([]);
    fireEvent.change(screen.getByLabelText('new tag key'), { target: { value: 'platform' } });
    fireEvent.change(screen.getByLabelText('new tag value'), { target: { value: 'zcu102' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add tag' }));
    expect(addMutate).toHaveBeenCalledWith(
      { key: 'platform', value: 'zcu102' },
      expect.anything(),
    );
  });

  it('edits a tag value', () => {
    renderEditor();
    fireEvent.click(screen.getByRole('button', { name: 'Edit hw' }));
    fireEvent.change(screen.getByLabelText('edit value for hw'), { target: { value: 'adrv9009' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save hw' }));
    expect(updateMutate).toHaveBeenCalledWith(
      { key: 'hw', value: 'adrv9009' },
      expect.anything(),
    );
  });

  it('deletes a tag after confirm', () => {
    renderEditor();
    fireEvent.click(screen.getByRole('button', { name: 'Delete hw' }));
    // first click asks to confirm; second click commits
    fireEvent.click(screen.getByRole('button', { name: 'Confirm delete hw' }));
    expect(deleteMutate).toHaveBeenCalledWith('hw', expect.anything());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/TagsEditor.test.tsx`
Expected: FAIL — cannot resolve `./TagsEditor`.

- [ ] **Step 3: Create the component**

Create `apps/web/src/components/TagsEditor.tsx`:

```typescript
import { Box, Button, Flex, Input, Stack, Text } from '@chakra-ui/react';
import { useState } from 'react';

import { useAddRunTag, useDeleteRunTag, useUpdateRunTag } from '../api/queries';
import type { RunTag } from '../api/types';

function TagRow({ runId, tag }: { runId: string; tag: RunTag }) {
  const update = useUpdateRunTag(runId);
  const del = useDeleteRunTag(runId);
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(tag.value);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = () => {
    setError(null);
    update.mutate(
      { key: tag.key, value },
      {
        onSuccess: () => setEditing(false),
        onError: () => setError('Could not update tag (it may no longer exist).'),
      },
    );
  };

  return (
    <Flex align="center" gap={2} wrap="wrap">
      <Text fontFamily="mono" fontSize="sm" fontWeight="600">
        {tag.key}
      </Text>
      <Text fontSize="sm">=</Text>
      {editing ? (
        <>
          <Input
            size="xs"
            maxW="180px"
            maxLength={500}
            aria-label={`edit value for ${tag.key}`}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <Button size="xs" colorPalette="blue" loading={update.isPending}
                  aria-label={`Save ${tag.key}`} onClick={save}>
            Save
          </Button>
          <Button size="xs" variant="ghost" aria-label={`Cancel ${tag.key}`}
                  onClick={() => { setEditing(false); setValue(tag.value); setError(null); }}>
            Cancel
          </Button>
        </>
      ) : (
        <>
          <Text fontFamily="mono" fontSize="sm">{tag.value}</Text>
          <Button size="xs" variant="outline" aria-label={`Edit ${tag.key}`}
                  onClick={() => { setValue(tag.value); setEditing(true); }}>
            Edit
          </Button>
          {confirmDelete ? (
            <Button size="xs" colorPalette="red" loading={del.isPending}
                    aria-label={`Confirm delete ${tag.key}`}
                    onClick={() => del.mutate(tag.key, {
                      onError: () => setError('Could not delete tag.'),
                    })}>
              Confirm delete
            </Button>
          ) : (
            <Button size="xs" variant="ghost" aria-label={`Delete ${tag.key}`}
                    onClick={() => setConfirmDelete(true)}>
              ✕
            </Button>
          )}
        </>
      )}
      {error && <Text fontSize="xs" color="red.400">{error}</Text>}
    </Flex>
  );
}

export function TagsEditor({ runId, tags }: { runId: string; tags: RunTag[] }) {
  const add = useAddRunTag(runId);
  const [key, setKey] = useState('');
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    if (!key.trim() || !value.trim()) return;
    add.mutate(
      { key: key.trim(), value: value.trim() },
      {
        onSuccess: () => { setKey(''); setValue(''); },
        onError: (e: unknown) => {
          const status = (e as { response?: { status?: number } })?.response?.status;
          setError(status === 409 ? 'Tag already exists — edit it instead.' : 'Could not add tag.');
        },
      },
    );
  };

  return (
    <Stack gap={2}>
      {tags.length === 0 ? (
        <Text fontSize="xs" color="var(--prism-text-faint)">none</Text>
      ) : (
        tags.map((t) => <TagRow key={t.key} runId={runId} tag={t} />)
      )}
      <Flex align="center" gap={2} wrap="wrap" mt={1}>
        <Input size="xs" maxW="140px" maxLength={100} placeholder="key"
               aria-label="new tag key" value={key} onChange={(e) => setKey(e.target.value)} />
        <Input size="xs" maxW="180px" maxLength={500} placeholder="value"
               aria-label="new tag value" value={value} onChange={(e) => setValue(e.target.value)} />
        <Button size="xs" colorPalette="blue" loading={add.isPending}
                aria-label="Add tag" onClick={submit}>
          Add tag
        </Button>
      </Flex>
      {error && <Box><Text fontSize="xs" color="red.400">{error}</Text></Box>}
    </Stack>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/TagsEditor.test.tsx`
Expected: PASS (4 tests). If a Chakra v3 prop is rejected, fix the component (not the test) and note it.

- [ ] **Step 5: Wire into RunDetailPage**

In `apps/web/src/pages/RunDetailPage.tsx`:
1. Add the import (with the other component imports): `import { TagsEditor } from '../components/TagsEditor';`
2. Replace the read-only Tags block. Find this block:

```tsx
      {label('Tags')}
      {run.tags.length === 0 ? (
        <Text fontSize="xs" color="var(--prism-text-faint)">
          none
        </Text>
      ) : (
        <Stack direction="row" gap={1} wrap="wrap">
          {run.tags.map((t) => (
            <Badge key={`${t.key}:${t.value}`} variant="outline" size="sm">
              {t.key}={t.value}
            </Badge>
          ))}
        </Stack>
      )}
```

and replace it with:

```tsx
      {label('Tags')}
      <TagsEditor runId={run.id} tags={run.tags} />
```

3. If `Badge` is now unused elsewhere in the file, remove it from the `@chakra-ui/react` import to satisfy eslint (check first — it may still be used for the status badge).

- [ ] **Step 6: Verify build, lint, and full unit suite**

Run: `npm run build && npm run lint && npx vitest run`
Expected: all pass, no regressions.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/TagsEditor.tsx apps/web/src/components/TagsEditor.test.tsx apps/web/src/pages/RunDetailPage.tsx
git commit -m "feat(web): inline tag editor on run detail page"
```

---

## Task 5: E2E test

**Files:**
- Create: `apps/web/e2e/run-tags.spec.ts`

- [ ] **Step 1: Write the e2e test**

Create `apps/web/e2e/run-tags.spec.ts` (mirror the login helper from `e2e/compare.spec.ts` and the axe helper):

```typescript
import { expect, test } from '@playwright/test';
import { expectNoSeriousAxeViolations } from './helpers/axe';

const EMAIL = process.env.PLAYWRIGHT_ADMIN_EMAIL ?? 'admin@example.com';
const PASSWORD = process.env.PLAYWRIGHT_ADMIN_PASSWORD ?? 'change-me-in-prod';

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.fill('input[type=email]', EMAIL);
  await page.fill('input[type=password]', PASSWORD);
  await page.click('button[type=submit]');
  await page.waitForURL((url) => url.pathname === '/');
}

test('add, edit, and delete a run tag from the run detail page', async ({ page }) => {
  await login(page);

  // Open the first run in the seeded `audio` project.
  await page.goto('/projects/audio');
  await page.waitForSelector('tbody tr');
  await page.locator('tbody tr a').first().click();
  await page.waitForURL(/\/runs\//);

  // The details panel (with the Tags section) must be visible; open it if collapsed.
  const addKey = page.getByLabel('new tag key');
  if (!(await addKey.isVisible())) {
    await page.getByRole('button', { name: /details/i }).first().click();
  }
  await expect(addKey).toBeVisible();

  // Add a tag.
  await addKey.fill('e2e_tag');
  await page.getByLabel('new tag value').fill('v1');
  await page.getByRole('button', { name: 'Add tag' }).click();
  await expect(page.getByText('e2e_tag')).toBeVisible();
  await expectNoSeriousAxeViolations(page);

  // Edit its value.
  await page.getByRole('button', { name: 'Edit e2e_tag' }).click();
  await page.getByLabel('edit value for e2e_tag').fill('v2');
  await page.getByRole('button', { name: 'Save e2e_tag' }).click();
  await expect(page.getByText('v2')).toBeVisible();

  // Delete it (two-step confirm).
  await page.getByRole('button', { name: 'Delete e2e_tag' }).click();
  await page.getByRole('button', { name: 'Confirm delete e2e_tag' }).click();
  await expect(page.getByText('e2e_tag')).toHaveCount(0);
  await expectNoSeriousAxeViolations(page);
});
```

> The run-detail details panel may be collapsed by default — the test opens it if the add-key field isn't visible. Confirm the toggle button's accessible name against `RunDetailPage.tsx` (the Tooltip mentions "Show or hide the run details panel"); adjust the `name: /details/i` matcher if needed.

- [ ] **Step 2: Verify it parses/lists (cannot run without the stack)**

Run: `npm run lint && npx playwright test --list e2e/run-tags.spec.ts`
Expected: lint clean; lists 1 test, no compile errors. (Do not run the full e2e unless the stack is up + seeded.)

- [ ] **Step 3: Commit**

```bash
git add apps/web/e2e/run-tags.spec.ts
git commit -m "test(web): e2e for run tag add/edit/delete"
```

---

## Final verification

- [ ] **Backend:** `cd apps/api && uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy src` — all green.
- [ ] **Frontend:** `cd apps/web && npx vitest run && npm run lint && npm run build` — all green.
- [ ] **E2E (stack up + seeded):** `npm run e2e -- run-tags.spec.ts` — passes, no serious axe violations.
- [ ] **Manual:** open a run, add a tag, edit its value, delete it; confirm the badge list updates and (for `hw`/`platform`/`boot_file`) the matrix wall reflects the change on its next refresh.
```
