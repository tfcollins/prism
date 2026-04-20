# Prism — Comparison & Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the comparison feature (overlay FFT/time-domain plots + pass/fail diff table) and harden+document the v1 release. Adds CSRF protection on multipart upload, an MkDocs site, a basic Playwright E2E, and merges `feat/walking-skeleton` to `main`.

**Architecture:** Comparison is a thin slice — `POST /api/v1/compare` accepts `{run_ids: [...]}`, returns aggregated diff (pass/fail per case) plus per-case waveform/FFT artifact pointers. Frontend `/compare?runs=a,b` page overlays Plotly traces from each run's matching artifact. CSRF is implemented via a double-submit cookie pattern (issued on login, required on state-changing endpoints). Docs are MkDocs-Material with the live OpenAPI spec embedded. Playwright runs against the docker stack in CI.

**Tech Stack:** Adds `mkdocs-material`, `mkdocs-swagger-ui-tag`, `@playwright/test`. No new runtime deps.

---

## Conventions

- Paths relative to repo root `/home/tcollins/dev/prism`.
- Pytest: `cd /home/tcollins/dev/prism/apps/api && uv run pytest -v`. Vitest: `cd /home/tcollins/dev/prism/apps/web && npm test`.
- TDD: failing test → impl → passing test → commit.
- Commits: Conventional Commits. **No `Co-Authored-By` lines.**
- Bash cwd may be pinned to a stub; always use absolute paths or explicit `cd`.

## Plan-3 review items folded in

- **CSRF on multipart upload** — Phase 0 (a multipart `POST /runs` endpoint is CSRF-reachable from a victim's browser; SameSite=Lax doesn't block forms)
- **`description` not nullable on Project** — kept as `""` default by intent; not changing.
- **JWT TTL** stays at 24 h; refresh endpoint deferred.

---

## Phase 0: CSRF protection

### Task 0.1: Issue + verify CSRF token

**Files:**
- Modify: `apps/api/src/prism_api/deps.py` (add `CSRF_COOKIE` constant + `csrf_protect` dependency)
- Modify: `apps/api/src/prism_api/routers/auth.py` (issue CSRF cookie on login; clear on logout)
- Modify: `apps/api/src/prism_api/routers/runs.py` (require `csrf_protect` on `POST /runs`)
- Modify: `apps/api/tests/test_auth_router.py` (assert CSRF cookie present after login)
- Create: `apps/api/tests/test_csrf.py` (uploads with/without csrf token, expects 403/201)

- [ ] **Step 1: Add the deps**

Append to `apps/api/src/prism_api/deps.py`:
```python
import secrets

CSRF_COOKIE = "prism_csrf"
CSRF_HEADER = "x-prism-csrf"


def issue_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_protect(request: Request) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get(CSRF_HEADER)
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "missing or invalid csrf token")
```

- [ ] **Step 2: Issue + clear in auth router**

In `apps/api/src/prism_api/routers/auth.py` `login()`, after `set_cookie(SESSION_COOKIE,...)`, add:
```python
from prism_api.deps import CSRF_COOKIE, issue_csrf_token
...
csrf_token = issue_csrf_token()
response.set_cookie(
    key=CSRF_COOKIE,
    value=csrf_token,
    httponly=False,            # JS must read it to echo in the header
    samesite=settings.cookie_samesite,
    secure=settings.cookie_secure,
    max_age=settings.jwt_ttl_minutes * 60,
    path="/",
)
```
And in `logout()`:
```python
response.delete_cookie(CSRF_COOKIE, path="/", samesite=settings.cookie_samesite, secure=settings.cookie_secure)
```

- [ ] **Step 3: Require it on `POST /runs`**

In `apps/api/src/prism_api/routers/runs.py` add `_csrf: None = Depends(csrf_protect)` to `upload_run` parameters and import `csrf_protect` from `prism_api.deps`.

- [ ] **Step 4: Update existing tests**

`apps/api/tests/test_auth_router.py` — append:
```python
def test_login_issues_csrf_cookie(client, seed_admin):
    r = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    assert r.status_code == 200
    assert "prism_csrf" in r.cookies
```

`apps/api/tests/test_runs_router.py` — update existing upload tests to set the CSRF header AND cookie. The `_login` helper should now extract the CSRF cookie value and the upload calls must pass `headers={"X-Prism-Csrf": <token>}`. Helper:
```python
def _login(client) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""
```
Then in each upload call:
```python
csrf = _login(client)
client.post("/api/v1/runs", files=..., data=..., headers={"X-Prism-Csrf": csrf})
```

Also update `apps/api/tests/test_runs_read.py` and `apps/api/tests/test_cases_router.py` and `apps/api/tests/test_artifacts_router.py` if they have upload calls — apply the same change.

- [ ] **Step 5: Add CSRF-specific test**

`apps/api/tests/test_csrf.py`:
```python
import json

from fastapi.testclient import TestClient


def test_upload_without_csrf_returns_403(client: TestClient, seed_admin) -> None:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", b"<testsuites/>", "application/xml")},
        data={"metadata": json.dumps({"project_slug": "audio", "name": "x"})},
    )
    assert resp.status_code == 403


def test_upload_with_mismatched_csrf_returns_403(client: TestClient, seed_admin) -> None:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", b"<testsuites/>", "application/xml")},
        data={"metadata": json.dumps({"project_slug": "audio", "name": "x"})},
        headers={"X-Prism-Csrf": "wrong-value"},
    )
    assert resp.status_code == 403
```

(Note: projects router does NOT require CSRF — it accepts JSON, not multipart, and SameSite=Lax blocks cross-origin JSON-body POSTs from a victim browser. We're protecting only the multipart upload pathway in v1.)

- [ ] **Step 6: Run all api tests**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest -v
```
Expected: all tests pass (now ~95 with the new csrf tests).

- [ ] **Step 7: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): CSRF double-submit cookie required on multipart upload"
```

---

### Task 0.2: Frontend echoes the CSRF header

**Files:**
- Modify: `apps/web/src/api/client.ts` (axios interceptor reads cookie + sets header)

- [ ] **Step 1: Update axios client**

`apps/web/src/api/client.ts`:
```ts
import axios from 'axios';

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

export const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const method = config.method?.toLowerCase();
  if (method && ['post', 'put', 'patch', 'delete'].includes(method)) {
    const csrf = readCookie('prism_csrf');
    if (csrf) {
      config.headers = config.headers ?? {};
      config.headers['X-Prism-Csrf'] = csrf;
    }
  }
  return config;
});
```

- [ ] **Step 2: Verify frontend tests still pass**

```bash
cd /home/tcollins/dev/prism/apps/web && npm test && npm run build && npm run lint
```

- [ ] **Step 3: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/web/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(web): axios echoes prism_csrf cookie as X-Prism-Csrf header"
```

---

## Phase 1: Compare backend

### Task 1.1: Compare schemas + endpoint

**Files:**
- Create: `apps/api/src/prism_api/schemas/compare.py`
- Create: `apps/api/src/prism_api/routers/compare.py`
- Modify: `apps/api/src/prism_api/main.py` (include router)
- Create: `apps/api/tests/test_compare_router.py`

- [ ] **Step 1: Write schemas**

`apps/api/src/prism_api/schemas/compare.py`:
```python
from pydantic import BaseModel, Field


class CompareRequest(BaseModel):
    run_ids: list[str] = Field(min_length=2, max_length=10)


class CaseDiff(BaseModel):
    classname: str
    name: str
    suite_name: str
    statuses: list[str | None]  # one entry per requested run, None = case absent in that run


class RunHeader(BaseModel):
    id: str
    name: str
    status: str
    pass_count: int
    fail_count: int


class CompareResponse(BaseModel):
    runs: list[RunHeader]
    cases: list[CaseDiff]
    pass_rate_delta: float | None  # (run[-1] - run[0]) / total, or None if zero divides
```

- [ ] **Step 2: Write the failing test**

`apps/api/tests/test_compare_router.py`:
```python
import io
import json
import zipfile

from fastapi.testclient import TestClient


def _login(client: TestClient) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def _upload(client: TestClient, csrf: str, name: str, junit_xml: bytes) -> str:
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("readme.log", "ctx\n")
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit_xml, "application/xml"), "archive": ("a.zip", arc.getvalue(), "application/zip")},
        data={"metadata": json.dumps({"project_slug": "audio", "name": name})},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


_BASE_JUNIT = b"""<?xml version="1.0"?><testsuites>
<testsuite name="dsp" tests="2" failures="0" time="0.1">
<testcase classname="codec" name="ok" time="0.05"/>
<testcase classname="codec" name="other" time="0.05"/>
</testsuite></testsuites>"""

_FAIL_ON_OTHER = b"""<?xml version="1.0"?><testsuites>
<testsuite name="dsp" tests="2" failures="1" time="0.1">
<testcase classname="codec" name="ok" time="0.05"/>
<testcase classname="codec" name="other" time="0.05"><failure message="x">t</failure></testcase>
</testsuite></testsuites>"""


def test_compare_two_runs(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    a = _upload(client, csrf, "a", _BASE_JUNIT)
    b = _upload(client, csrf, "b", _FAIL_ON_OTHER)

    resp = client.post(
        "/api/v1/compare",
        json={"run_ids": [a, b]},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [r["id"] for r in body["runs"]] == [a, b]
    statuses = {(c["suite_name"], c["name"]): c["statuses"] for c in body["cases"]}
    assert statuses[("dsp", "ok")] == ["pass", "pass"]
    assert statuses[("dsp", "other")] == ["pass", "fail"]


def test_compare_rejects_single_run(client: TestClient, seed_admin) -> None:
    csrf = _login(client)
    resp = client.post(
        "/api/v1/compare",
        json={"run_ids": ["00000000-0000-0000-0000-000000000000"]},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 422


def test_compare_unknown_run_404(client: TestClient, seed_admin) -> None:
    csrf = _login(client)
    resp = client.post(
        "/api/v1/compare",
        json={"run_ids": ["00000000-0000-0000-0000-000000000000", "11111111-1111-1111-1111-111111111111"]},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 404
```

- [ ] **Step 3: Implement router**

`apps/api/src/prism_api/routers/compare.py`:
```python
"""Compare runs."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from prism_api.deps import csrf_protect, current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.runs import RunRepo
from prism_api.repos.suites import CaseRepo, SuiteRepo
from prism_api.schemas.compare import CaseDiff, CompareRequest, CompareResponse, RunHeader

router = APIRouter(prefix="/api/v1/compare", tags=["compare"])


@router.post("", response_model=CompareResponse)
def compare_runs(
    body: CompareRequest,
    _: User = Depends(current_user),
    __: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
) -> CompareResponse:
    runs_repo = RunRepo(session)
    suites_repo = SuiteRepo(session)
    cases_repo = CaseRepo(session)

    runs = []
    for run_id in body.run_ids:
        run = runs_repo.get_by_id(run_id)
        if run is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"run {run_id} not found")
        counts = runs_repo.aggregate_counts_by_run(run.id)
        runs.append(
            RunHeader(
                id=run.id, name=run.name, status=run.status.value,
                pass_count=counts["pass_count"], fail_count=counts["fail_count"],
            )
        )

    # Build per-run case-status map: {(suite_name, case_name): status}
    per_run_status: list[dict[tuple[str, str], str]] = []
    all_keys: set[tuple[str, str]] = set()
    for run_id in body.run_ids:
        m: dict[tuple[str, str], str] = {}
        for suite in suites_repo.list_by_run(run_id):
            for case in cases_repo.list_by_suite(suite.id):
                key = (suite.name, case.name)
                m[key] = case.status.value
                all_keys.add(key)
        per_run_status.append(m)

    cases = sorted(
        [
            CaseDiff(
                suite_name=key[0], classname="", name=key[1],
                statuses=[m.get(key) for m in per_run_status],
            )
            for key in all_keys
        ],
        key=lambda c: (c.suite_name, c.name),
    )

    # pass-rate delta: (last.pass / total) - (first.pass / total)
    pr_delta: float | None
    first_total = runs[0].pass_count + runs[0].fail_count
    last_total = runs[-1].pass_count + runs[-1].fail_count
    if first_total == 0 or last_total == 0:
        pr_delta = None
    else:
        pr_delta = (runs[-1].pass_count / last_total) - (runs[0].pass_count / first_total)

    return CompareResponse(runs=runs, cases=cases, pass_rate_delta=pr_delta)
```

- [ ] **Step 4: Wire into main.py**

```python
from prism_api.routers import compare as compare_router
...
app.include_router(compare_router.router)
```

- [ ] **Step 5: Run tests (PASS)**

- [ ] **Step 6: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): POST /api/v1/compare — pass/fail diff across N runs"
```

---

## Phase 2: Compare frontend

### Task 2.1: Hook + page

**Files:**
- Modify: `apps/web/src/api/types.ts` (add `CompareResponse`, `RunHeader`, `CaseDiff`)
- Modify: `apps/web/src/api/queries.ts` (add `useCompare(runIds: string[])` mutation-style fetch)
- Create: `apps/web/src/pages/ComparePage.tsx`
- Modify: `apps/web/src/App.tsx` (add `/compare` route)
- Modify: `apps/web/src/components/Sidebar.tsx` (add "Compare" nav item)
- Modify: `apps/web/src/components/RunsTable.tsx` (add a checkbox column + "Compare selected" floating button)

- [ ] **Step 1: Append types**

In `apps/web/src/api/types.ts`:
```ts
export interface RunHeader {
  id: string;
  name: string;
  status: RunStatus;
  pass_count: number;
  fail_count: number;
}

export interface CaseDiff {
  suite_name: string;
  classname: string;
  name: string;
  statuses: (string | null)[];
}

export interface CompareResponse {
  runs: RunHeader[];
  cases: CaseDiff[];
  pass_rate_delta: number | null;
}
```

- [ ] **Step 2: Add query hook**

Append to `apps/web/src/api/queries.ts`:
```ts
import type { CompareResponse } from './types';

export function useCompare(runIds: string[]) {
  return useQuery({
    queryKey: ['compare', runIds.slice().sort().join(',')],
    queryFn: async () => (await api.post<CompareResponse>('/compare', { run_ids: runIds })).data,
    enabled: runIds.length >= 2,
  });
}
```

- [ ] **Step 3: ComparePage**

`apps/web/src/pages/ComparePage.tsx`:
```tsx
import { Badge, Box, Heading, Stack, Table, Text } from '@chakra-ui/react';
import { useSearchParams } from 'react-router-dom';

import { useCompare } from '../api/queries';
import { AppShell } from '../components/AppShell';

const STATUS_COLOR: Record<string, string> = {
  pass: 'green.300',
  fail: 'red.300',
  error: 'red.300',
  skip: 'gray.400',
};

export function ComparePage() {
  const [params] = useSearchParams();
  const runIds = (params.get('runs') ?? '').split(',').filter(Boolean);
  const q = useCompare(runIds);

  return (
    <AppShell>
      <Heading size="lg" mb={2}>Compare</Heading>
      <Text fontSize="sm" color="gray.500" mb={4}>{runIds.length} runs selected</Text>

      {runIds.length < 2 && (
        <Text>Select at least 2 runs from the dashboard, then use the Compare button.</Text>
      )}
      {q.isLoading && <Text>Loading…</Text>}
      {q.isError && <Text color="red.400">Failed to load comparison</Text>}
      {q.data && (
        <Stack gap={4}>
          <Box>
            <Text fontSize="sm" color="gray.400">Pass rate Δ:&nbsp;
              {q.data.pass_rate_delta === null
                ? 'n/a'
                : `${(q.data.pass_rate_delta * 100).toFixed(1)}%`}
            </Text>
          </Box>
          <Table.Root variant="outline" size="sm">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Suite</Table.ColumnHeader>
                <Table.ColumnHeader>Case</Table.ColumnHeader>
                {q.data.runs.map((r) => (
                  <Table.ColumnHeader key={r.id}>{r.name}</Table.ColumnHeader>
                ))}
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {q.data.cases.map((c) => (
                <Table.Row key={`${c.suite_name}/${c.name}`}>
                  <Table.Cell>{c.suite_name}</Table.Cell>
                  <Table.Cell>{c.name}</Table.Cell>
                  {c.statuses.map((s, i) => (
                    <Table.Cell key={i}>
                      {s ? (
                        <Badge colorPalette={s === 'pass' ? 'green' : s === 'skip' ? 'gray' : 'red'}>{s}</Badge>
                      ) : (
                        <Text fontSize="xs" color="gray.500">absent</Text>
                      )}
                    </Table.Cell>
                  ))}
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </Stack>
      )}
    </AppShell>
  );
}
```

- [ ] **Step 4: Add `/compare` route in App.tsx**

```tsx
import { ComparePage } from './pages/ComparePage';
// ...
<Route path="/compare" element={<ProtectedRoute><ComparePage /></ProtectedRoute>} />
```

- [ ] **Step 5: Add Compare nav link**

Update `apps/web/src/components/Sidebar.tsx` `navItems`:
```ts
const navItems = [
  { to: '/', label: 'Runs' },
  { to: '/projects', label: 'Projects' },
  { to: '/compare', label: 'Compare' },
];
```

- [ ] **Step 6: Add multi-select to RunsTable**

Replace `apps/web/src/components/RunsTable.tsx` to track selected IDs and render a "Compare selected" button at the bottom:
```tsx
import { Box, Button, Checkbox, Flex, Table, Text } from '@chakra-ui/react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import type { RunListItem } from '../api/types';

const STATUS_COLOR: Record<string, string> = {
  pass: '#48bb78',
  fail: '#f56565',
  mixed: '#ed8936',
  error: '#f56565',
  pending: '#a0aec0',
};

export function RunsTable({ runs }: { runs: RunListItem[] }) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const navigate = useNavigate();

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
  }

  if (runs.length === 0) {
    return <Text color="gray.500">No runs yet.</Text>;
  }

  return (
    <Box>
      <Table.Root variant="outline" size="sm">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeader></Table.ColumnHeader>
            <Table.ColumnHeader>Status</Table.ColumnHeader>
            <Table.ColumnHeader>Run</Table.ColumnHeader>
            <Table.ColumnHeader>Pass</Table.ColumnHeader>
            <Table.ColumnHeader>Fail</Table.ColumnHeader>
            <Table.ColumnHeader>Tags</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {runs.map((r) => (
            <Table.Row key={r.id}>
              <Table.Cell>
                <Checkbox.Root
                  checked={selected.has(r.id)}
                  onCheckedChange={() => toggle(r.id)}
                >
                  <Checkbox.Control />
                </Checkbox.Root>
              </Table.Cell>
              <Table.Cell>
                <Box display="inline-block" w="8px" h="8px" borderRadius="50%" bg={STATUS_COLOR[r.status] ?? '#a0aec0'} mr={2} />
                {r.status}
              </Table.Cell>
              <Table.Cell>
                <Link to={`/runs/${r.id}`} style={{ color: '#63b3ed' }}>{r.name}</Link>
              </Table.Cell>
              <Table.Cell>{r.pass_count}</Table.Cell>
              <Table.Cell>{r.fail_count}</Table.Cell>
              <Table.Cell>
                {r.tags.map((t) => (
                  <Text as="span" key={`${t.key}:${t.value}`} mr={2} fontFamily="mono" fontSize="xs">
                    {t.key}={t.value}
                  </Text>
                ))}
              </Table.Cell>
            </Table.Row>
          ))}
        </Table.Body>
      </Table.Root>
      {selected.size >= 2 && (
        <Flex mt={3} justify="flex-end">
          <Button
            colorPalette="blue"
            size="sm"
            onClick={() => navigate(`/compare?runs=${Array.from(selected).join(',')}`)}
          >
            Compare {selected.size} runs
          </Button>
        </Flex>
      )}
    </Box>
  );
}
```

- [ ] **Step 7: Build + test + lint**

```bash
cd /home/tcollins/dev/prism/apps/web && npm test && npm run build && npm run lint
```

- [ ] **Step 8: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/web/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(web): compare page + multi-select on runs table"
```

---

## Phase 3: MkDocs documentation

### Task 3.1: MkDocs scaffold + basic content

**Files:**
- Create: `docs/mkdocs.yml`
- Create: `docs/docs/index.md`
- Create: `docs/docs/getting-started.md`
- Create: `docs/docs/architecture.md`
- Create: `docs/docs/data-model.md`
- Create: `docs/docs/api.md`
- Create: `docs/docs/development.md`
- Create: `docs/docs/ci-integration.md`

- [ ] **Step 1: Write `docs/mkdocs.yml`**

```yaml
site_name: Prism
site_description: Self-hostable test results management & visualization
repo_url: https://github.com/yourorg/prism
theme:
  name: material
  palette:
    - scheme: slate
      primary: blue
      accent: cyan
  features:
    - navigation.sections
    - navigation.expand
    - content.code.copy

nav:
  - Home: index.md
  - Getting started: getting-started.md
  - Architecture: architecture.md
  - Data model: data-model.md
  - API reference: api.md
  - Development: development.md
  - CI integration: ci-integration.md

markdown_extensions:
  - pymdownx.superfences
  - pymdownx.highlight
  - pymdownx.inlinehilite
  - pymdownx.tabbed:
      alternate_style: true
  - admonition
  - tables
```

- [ ] **Step 2: Write the markdown pages**

`docs/docs/index.md`:
```markdown
# Prism

Self-hostable web app for managing and visualizing test results — JUnit XML pass/fail metadata plus measurement artifacts (waveforms, FFTs, logs).

**Why Prism?** When your test suite produces *both* pass/fail outcomes and signal data — e.g. DSP pipelines, RF benches, audio codecs — most CI dashboards drop the signal data on the floor. Prism stores it, lets you browse it, and overlay it across runs.

## Quickstart

```bash
git clone <repo>
cd prism
cp deploy/.env.example deploy/.env
make up
open http://localhost:8180
```

Default login is in `deploy/.env`. See [Getting started](getting-started.md) for next steps.
```

`docs/docs/getting-started.md`:
```markdown
# Getting started

## Prerequisites

- Docker + Docker Compose
- A free port for each service: 8000 (api), 8180 (web), 5433 (postgres), 6380 (redis), 9100/9101 (minio). Override any in `deploy/.env`.

## First run

1. `cp deploy/.env.example deploy/.env`
2. Edit `deploy/.env`: set `JWT_SECRET` to a random ≥32-character string, change `ADMIN_PASSWORD`.
3. `make up`
4. Visit http://localhost:8180 — log in with the admin email/password from `.env`.

## Upload a run via curl

```bash
# Login (saves cookies including the CSRF token)
curl -s -c /tmp/p.txt -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"...your password..."}' \
  http://localhost:8000/api/v1/auth/login

# Read CSRF token out of the cookie jar
CSRF=$(awk -F'\t' '/prism_csrf/{print $7}' /tmp/p.txt)

# Create a project
curl -s -b /tmp/p.txt -H 'Content-Type: application/json' \
  -H "X-Prism-Csrf: $CSRF" \
  -d '{"slug":"my-project","name":"My Project"}' \
  http://localhost:8000/api/v1/projects

# Upload a run (junit.xml + optional zip of waveforms)
curl -s -b /tmp/p.txt -H "X-Prism-Csrf: $CSRF" \
  -F 'junit=@./junit.xml;type=application/xml' \
  -F 'archive=@./artifacts.zip;type=application/zip' \
  -F 'metadata={"project_slug":"my-project","name":"build-42","tags":{"branch":"main"}}' \
  http://localhost:8000/api/v1/runs
```

## File naming convention for archive uploads

Files inside the archive follow `{suite}__{case}__{label}.{ext}`:

- `dsp__sine_sweep_1khz__waveform.csv` → attached to suite `dsp`, case `sine_sweep_1khz`
- `dsp__suite-log.log` → attached to suite `dsp`
- `readme.log` → attached to the run

Supported artifact types: `*.xml` (JUnit), `*.csv` `*.npy` `*.h5` (waveforms), `*.wav`, `*.png`, `*.log`. Anything else is stored as `other_binary`.

## Waveform CSV format

Single column of floats, optionally with a `# sample_rate=<int>` comment on the first line:

```
# sample_rate=48000
0.000000
0.130526
0.258819
...
```
```

`docs/docs/architecture.md`:
```markdown
# Architecture

```
┌─────────┐     ┌──────┐     ┌──────────┐     ┌──────────┐
│ Browser │────▶│ web  │────▶│   api    │◀───▶│ postgres │
└─────────┘     │nginx │     │ FastAPI  │     └──────────┘
                └──────┘     └──────────┘
                                  │  ▲
                                  ▼  │
                              ┌──────────┐    ┌─────────┐
                              │  redis   │◀──▶│ worker  │
                              │  broker  │    │ Celery  │
                              └──────────┘    └─────────┘
                                  │                │
                                  ▼                ▼
                              ┌──────────────────────┐
                              │     minio (S3)       │
                              └──────────────────────┘
```

## Services

| Service  | Tech                        | Responsibility |
|----------|-----------------------------|----------------|
| `web`    | React + Vite + Chakra UI v3 | SPA: login, browse runs, plots, compare |
| `api`    | FastAPI + SQLAlchemy        | REST + auth + upload coordination |
| `worker` | Celery                      | JUnit parsing, archive extraction, FFT computation |
| `postgres` | Postgres 16                | Metadata: projects, runs, suites, cases, artifacts, users |
| `minio`  | MinIO                        | Raw artifact bytes (content-addressed) + derived FFT cache |
| `redis`  | Redis 7                      | Celery broker + result backend |

## Data flow on upload

1. Browser POSTs `multipart/form-data` to `api`: junit XML + optional zip + JSON metadata. The `X-Prism-Csrf` header must match the `prism_csrf` cookie issued at login.
2. `api` writes a `TestRun(status=pending)` row, uploads the JUnit XML and (if present) zip to MinIO under content-addressed keys, dispatches `prism.ingest_run` to Celery via Redis.
3. `worker` pulls the task, fetches blobs from MinIO, parses JUnit (`junitparser`), extracts the zip, identifies each file's kind via magic bytes + extension, attaches each to its run/suite/case via the `{suite}__{case}__{label}` filename convention, and sets the run's final `status` (pass/fail/mixed/error).
4. Browser polls `GET /api/v1/runs/:id` to see the status flip from `pending`.

## Data flow on plot view

1. Browser navigates to a case → calls `GET /api/v1/cases/:id`, sees its attached `Artifact` rows.
2. For a waveform artifact, browser calls `GET /api/v1/artifacts/:id/waveform?downsample=N`. The api fetches the raw bytes from MinIO, parses with the right loader, runs `downsample_for_plot`, returns JSON samples.
3. For an FFT, browser calls `GET /api/v1/artifacts/:id/fft?window=&nfft=&overlap=`. The api looks up `DerivedArtifact` by `(source_hash, params_hash)`. Cache hit → load `.npz` from MinIO. Cache miss → compute Welch FFT, store as `.npz`, create `DerivedArtifact` row, return JSON.
```

`docs/docs/data-model.md`:
```markdown
# Data model

```
User
Project ─< TestRun ─< TestSuite ─< TestCase
              │                       │
              ├─< RunTag (k/v)        │
              └─< Artifact >──────────┘
                     │
                     └─< DerivedArtifact (FFT cache, thumbnails)
```

| Table             | Purpose |
|-------------------|---------|
| `users`           | Authentication; flat permission model |
| `projects`        | Top-level grouping, slug + name |
| `test_runs`       | One per upload; tracks ingest status, links project + creator |
| `run_tags`        | Arbitrary key/value tags on a run (branch, sha, hardware) |
| `test_suites`     | Per-suite aggregates within a run |
| `test_cases`      | Individual case + outcome + failure detail |
| `artifacts`       | File metadata (kind, hash, MinIO key); polymorphic owner (run/suite/case) |
| `derived_artifacts` | Cached computations (FFT) keyed by source + params |

Artifacts are content-addressed: identical bytes across runs share one MinIO object. The polymorphic `owner_type` column avoids three near-identical FK columns.
```

`docs/docs/api.md`:
```markdown
# API reference

The full OpenAPI 3 spec is auto-generated by FastAPI and served live at `/api/docs` (Swagger UI) and `/api/openapi.json` (raw schema) on a running stack.

## Endpoint summary

### Auth
- `POST /api/v1/auth/login` — set session + CSRF cookies
- `POST /api/v1/auth/logout` — clear cookies
- `GET /api/v1/auth/me` — current user

### Users
- `GET /api/v1/users` — list
- `POST /api/v1/users` — create (any authenticated user)
- `DELETE /api/v1/users/{id}` — delete (blocked for self / last user)

### Projects
- `GET /api/v1/projects` — list
- `POST /api/v1/projects` — create
- `GET /api/v1/projects/{slug}` — detail

### Runs
- `GET /api/v1/runs?project=&status=&limit=` — paginated list
- `POST /api/v1/runs` — multipart upload (CSRF-protected)
- `GET /api/v1/runs/{id}` — detail with suites

### Suites + cases
- `GET /api/v1/suites/{id}/cases`
- `GET /api/v1/cases/{id}` (returns attached artifacts)

### Artifacts
- `GET /api/v1/artifacts/{id}` — metadata
- `GET /api/v1/artifacts/{id}/download` — 307 redirect to signed MinIO URL
- `GET /api/v1/artifacts/{id}/waveform?downsample=N` — JSON time-domain samples
- `GET /api/v1/artifacts/{id}/fft?window=hann&nfft=1024&overlap=0.5` — JSON spectrum (cached)

### Compare
- `POST /api/v1/compare` — body `{run_ids: [a, b, ...]}` (CSRF-protected)
```

`docs/docs/development.md`:
```markdown
# Development

## Local setup

```bash
# Backend
cd apps/api
uv sync --group dev
uv run pytest -v

# Frontend
cd apps/web
npm install
npm test
npm run build
```

## Running just the dependencies

If you want to run `uvicorn` directly (faster reload than docker rebuilds):

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env up -d postgres redis minio
PRISM_DATABASE_URL=postgresql+psycopg://prism:...@localhost:5433/prism \
PRISM_S3_ENDPOINT=http://localhost:9100 \
PRISM_S3_ACCESS_KEY=prism PRISM_S3_SECRET_KEY=... \
PRISM_S3_BUCKET=prism PRISM_REDIS_URL=redis://localhost:6380/0 \
PRISM_JWT_SECRET=dev-only-replace-with-32-plus-random-chars-please \
uv run uvicorn prism_api.main:app --reload
```

## Quality gates

`make lint` runs `ruff` + `mypy --strict` + `eslint`. CI runs the same on every PR.

## Adding a migration

```bash
cd apps/api
uv run alembic revision --autogenerate -m "describe change"
# Review/edit the generated file, then:
uv run alembic upgrade head
```
```

`docs/docs/ci-integration.md`:
```markdown
# Integrating with your CI

## Generic shell

```bash
# After your test suite produces junit.xml, optionally bundle artifacts:
zip -r artifacts.zip waveforms/ logs/

curl -s -c /tmp/p.txt -H 'Content-Type: application/json' \
  -d "{\"email\":\"$PRISM_EMAIL\",\"password\":\"$PRISM_PASSWORD\"}" \
  "$PRISM_URL/api/v1/auth/login"

CSRF=$(awk -F'\t' '/prism_csrf/{print $7}' /tmp/p.txt)

curl -fs -b /tmp/p.txt -H "X-Prism-Csrf: $CSRF" \
  -F "junit=@junit.xml;type=application/xml" \
  -F "archive=@artifacts.zip;type=application/zip" \
  -F "metadata={\"project_slug\":\"$PROJECT\",\"name\":\"$BUILD_ID\",\"tags\":{\"branch\":\"$GIT_BRANCH\",\"sha\":\"$GIT_SHA\"}}" \
  "$PRISM_URL/api/v1/runs"
```

## GitHub Actions example

```yaml
- name: Upload to Prism
  if: always()  # upload even on test failures
  env:
    PRISM_URL: ${{ secrets.PRISM_URL }}
    PRISM_EMAIL: ${{ secrets.PRISM_EMAIL }}
    PRISM_PASSWORD: ${{ secrets.PRISM_PASSWORD }}
  run: ./scripts/upload-to-prism.sh
```

Note: a long-lived Prism user account for CI is the simplest pattern in v1. API tokens are planned for a future release.
```

- [ ] **Step 3: Add a docs Dockerfile + compose service for live preview**

Append to `deploy/docker-compose.dev.yml`:
```yaml
  docs:
    image: squidfunk/mkdocs-material:latest
    volumes:
      - ../docs:/docs
    ports: ["${DOCS_HOST_PORT:-8181}:8000"]
    command: ["serve", "--dev-addr=0.0.0.0:8000"]
```

Add `DOCS_HOST_PORT=8181` to `deploy/.env.example`.

- [ ] **Step 4: Smoke-test the docs build**

```bash
docker run --rm -v /home/tcollins/dev/prism/docs:/docs squidfunk/mkdocs-material:latest build --strict
```
Expected: `INFO - Documentation built in <site>` with no warnings.

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add docs/ deploy/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "docs: MkDocs Material site (getting-started / architecture / data model / api / dev / ci)"
```

---

### Task 3.2: Docs CI workflow

**Files:**
- Create: `.github/workflows/docs.yml`

- [ ] **Step 1: Write the workflow**

`.github/workflows/docs.yml`:
```yaml
name: docs

on:
  push:
    branches: [main]
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build docs
        run: docker run --rm -v ${{ github.workspace }}/docs:/docs squidfunk/mkdocs-material:latest build --strict
```

- [ ] **Step 2: Commit**

```bash
cd /home/tcollins/dev/prism && git add .github/workflows/docs.yml && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "ci: docs build workflow"
```

---

## Phase 4: Playwright E2E (one golden path)

### Task 4.1: Playwright scaffold + login spec

**Files:**
- Create: `apps/web/playwright.config.ts`
- Create: `apps/web/e2e/login.spec.ts`
- Modify: `apps/web/package.json` (add `e2e` script)

- [ ] **Step 1: Install Playwright**

```bash
cd /home/tcollins/dev/prism/apps/web && npm install -D @playwright/test && npx playwright install --with-deps chromium
```

- [ ] **Step 2: Write playwright config**

`apps/web/playwright.config.ts`:
```ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:8180',
    headless: true,
    screenshot: 'only-on-failure',
  },
  reporter: [['list']],
});
```

- [ ] **Step 3: Write login spec**

`apps/web/e2e/login.spec.ts`:
```ts
import { expect, test } from '@playwright/test';

const EMAIL = process.env.PLAYWRIGHT_ADMIN_EMAIL ?? 'admin@example.com';
const PASSWORD = process.env.PLAYWRIGHT_ADMIN_PASSWORD ?? 'change-me-in-prod';

test('login redirects to dashboard and shows projects nav', async ({ page }) => {
  await page.goto('/login');
  await page.fill('input[type=email]', EMAIL);
  await page.fill('input[type=password]', PASSWORD);
  await page.click('button[type=submit]');
  await expect(page.getByRole('heading', { name: /projects/i })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Compare' })).toBeVisible();
});

test('logout clears session and bounces to login', async ({ page }) => {
  await page.goto('/login');
  await page.fill('input[type=email]', EMAIL);
  await page.fill('input[type=password]', PASSWORD);
  await page.click('button[type=submit]');
  await expect(page.getByRole('heading', { name: /projects/i })).toBeVisible();
  await page.click('button:has-text("Sign out")');
  await expect(page).toHaveURL(/\/login$/);
});
```

- [ ] **Step 4: Add npm script**

In `apps/web/package.json` `scripts`:
```json
"e2e": "playwright test"
```

- [ ] **Step 5: Smoke-test locally**

```bash
cd /home/tcollins/dev/prism/apps/web && npm run e2e
```
Expected: 2 passing (assumes the dev stack is running on the default ports).

- [ ] **Step 6: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/web/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "test(web): Playwright golden-path login + logout"
```

---

### Task 4.2: E2E CI workflow

**Files:**
- Create: `.github/workflows/e2e.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: e2e

on:
  push:
    branches: [main]
  pull_request:

jobs:
  playwright:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Generate .env
        run: cp deploy/.env.example deploy/.env
      - name: Bring up the stack
        run: docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env up -d --build
      - name: Wait for api
        run: |
          for i in {1..60}; do
            if curl -sf http://localhost:8000/api/v1/health; then break; fi
            sleep 2
          done
      - name: Wait for web
        run: |
          for i in {1..60}; do
            if curl -sf http://localhost:8180; then break; fi
            sleep 2
          done
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: apps/web/package-lock.json
      - working-directory: apps/web
        run: |
          npm ci
          npx playwright install --with-deps chromium
          npm run e2e
        env:
          PLAYWRIGHT_BASE_URL: http://localhost:8180
          PLAYWRIGHT_ADMIN_EMAIL: admin@example.com
          PLAYWRIGHT_ADMIN_PASSWORD: change-me-in-prod
      - if: always()
        run: docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env logs --tail=200
```

- [ ] **Step 2: Commit**

```bash
cd /home/tcollins/dev/prism && git add .github/workflows/e2e.yml && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "ci: end-to-end Playwright workflow"
```

---

## Phase 5: Final smoke + merge

### Task 5.1: Full-stack rebuild + smoke

Manual — no commit.

- [ ] **Step 1: Rebuild + relaunch**

```bash
cd /home/tcollins/dev/prism && \
  docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env down && \
  docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env up -d --build
```

- [ ] **Step 2: Visit `http://localhost:8180`**, log in, navigate to dashboard, select 2+ runs via checkboxes, click "Compare N runs" — should land on `/compare?runs=...` and show the diff table.

- [ ] **Step 3: Visit `http://localhost:8181`** (the docs site, if you brought up the docs service).

- [ ] **Step 4: Run the API + frontend test suites one more time end-to-end**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest -v
cd /home/tcollins/dev/prism/apps/web && npm test && npm run build && npm run lint
```

---

### Task 5.2: Tag v0.4.0 and merge

- [ ] **Step 1: Move the tag**

```bash
cd /home/tcollins/dev/prism && git tag -d v0.1.0-walking-skeleton 2>&1 || true
git tag -a v0.4.0-rc1 -m "Prism v0.4.0-rc1 — walking skeleton + ingest + browsing/DSP + compare + polish"
```

- [ ] **Step 2: Merge `feat/walking-skeleton` → `main`**

```bash
cd /home/tcollins/dev/prism && git checkout main && git merge --no-ff feat/walking-skeleton -m "Merge feat/walking-skeleton — Prism v0.4.0-rc1"
git log --oneline | head -10
```

(If `main` doesn't exist, create it via `git branch main feat/walking-skeleton` first.)

---

## What's deferred to a future plan

- **Build & publish images** (`build-images.yml`) — push tagged `prism-api`/`prism-web` images to GHCR
- **API tokens / PATs** for CI uploads (replace the long-lived password)
- **Pagination** on `/runs` list (currently `limit` only — no cursor)
- **Comparison overlay plots** (current compare view is the diff table only — overlaid Plotly traces would be the next iteration)
- **Custom DSP knobs** (windowing options, time-window selection)
- **Run + artifact retention policies**
- **Multi-tenant orgs / RBAC**
