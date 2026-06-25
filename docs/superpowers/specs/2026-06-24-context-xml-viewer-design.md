# Design: libiio context-XML viewer

Date: 2026-06-24

## Problem

Tests (e.g. pyadi-iio emulated devices) attach a **libiio context XML** that
describes the IIO context — devices, channels, and attributes. Prism cannot
surface these: `detect_kind` maps every `.xml` to `JUNIT_XML`, so a context dump
is misclassified, and there is no viewer. We want to recognise context XML and
let users view it (a drill-down tree **and** the raw source) and download it,
both per-test and at the run level — analogous to the boot-log viewer.

## Context format

A libiio context XML opens with `<?xml …?>`, then `<!DOCTYPE context [ … ]>`,
then the root `<context name="…" description="…">` containing:

```xml
<context name="local" description="Emulated Context">
  <context-attribute name="…" value="…"/>
  <device id="iio:device0" name="ad7291">
    <attribute name="…" value="…"/>
    <channel id="voltage0" type="input" name="…">
      <scan-element index="0" format="be:u12/16&gt;&gt;0"/>
      <attribute name="raw" value="2048"/>
    </channel>
  </device>
</context>
```

## Decisions (from brainstorming)

- **Placement:** both the test case view and a full-width run-level section.
- **Display:** both a structured, expandable device → channel → attribute tree
  ("dig into") and a raw XML view, toggled within the same viewer.

## Backend

`detect_kind` is the enabler.

- Add `ArtifactKind.IIO_CONTEXT_XML = "iio_context_xml"`. The `kind` column is
  `Enum(ArtifactKind, native_enum=False)` (stored as a string), so **no Alembic
  migration** is needed.
- In `detect_kind`, for a `.xml` suffix, sniff the head: if it contains
  `<!doctype context` (case-insensitive; libiio always emits it) or a root
  `<context ` / `<context>`, return `IIO_CONTEXT_XML`; otherwise `JUNIT_XML`.
  JUnit never carries `<!DOCTYPE context`, so there is no false-positive risk.
  This path runs only for **archive** files — the main JUnit upload is created
  with `kind=JUNIT_XML` directly in `ingest.py` and never goes through
  `detect_kind`.
- `IIO_CONTEXT_XML` is **not** added to `FIGURE_KINDS`, so it does not affect the
  runs-list "figures" badge.

Tests:

- `detect_kind` returns `IIO_CONTEXT_XML` for a context head and `JUNIT_XML` for
  a `<testsuites>` head.
- Ingest: an archive containing `context.xml` produces a run-scoped artifact with
  `kind == "iio_context_xml"`.

## Frontend

### Parser — `lib/iioContext.ts`

`parseContext(xml: string): ParsedContext | null` using the browser `DOMParser`.

```ts
interface CtxAttr { name: string; value: string }
interface CtxChannel { id: string; type: string; name: string | null; attributes: CtxAttr[] }
interface CtxDevice { id: string; name: string | null; attributes: CtxAttr[]; channels: CtxChannel[] }
interface ParsedContext {
  name: string | null;
  description: string | null;
  contextAttributes: CtxAttr[];
  devices: CtxDevice[];
}
```

Returns `null` when the document has no `<context>` root or a parser error
(`<parsererror>`), so the viewer can fall back to the raw view. Pure and
unit-tested.

### `ContextXmlViewer.tsx`

A self-contained collapsible block (Chakra `Accordion`, one root item) reused in
both placements. Props: `{ artifactId: string; filename: string }`.

- **Header:** filename + device count (count shown once the XML has loaded).
- **On expand (lazy):** fetch the raw XML via the existing
  `useArtifactRaw(artifactId, open)`; then a **Tree / Raw** segmented toggle:
  - **Tree** (default): `parseContext` result rendered as expandable nodes —
    context-attributes, then each **device** (expand → its attributes +
    channels), each **channel** (expand → its attributes). Expansion state is
    local React state per node. If `parseContext` returns `null`, show a notice
    and fall back to the Raw view.
  - **Raw:** the raw XML text in a scrollable monospace block.
  - **Download:** `<a href="/api/v1/artifacts/{artifactId}/raw"
    download="{filename}">` — same-origin GET, carries the auth cookie.
- Loading / error / empty states mirror the boot-log viewer.

### Placement

- **Case view** (`RunDetailPage`): from `caseQuery.data.artifacts`, render a
  `ContextXmlViewer` for each artifact with `kind === 'iio_context_xml'`, and
  exclude those from the existing "Attached files" (`otherArtifacts`) list.
- **Run level** (`RunDetailPage` main column, beside the Boot-log section): a
  full-width **"Context"** section listing run-scoped context artifacts (from
  `runArtifactsQuery.data`, `kind === 'iio_context_xml'`), each a
  `ContextXmlViewer`. Renders nothing when there are none.

Reuses `useArtifactRaw` from the boot-log work; no new query hook.

## Testing

- **Backend:** `detect_kind` (context vs junit), ingest archived `context.xml`
  → `iio_context_xml`.
- **Frontend:**
  - `lib/iioContext.test.ts` — parse a representative context: assert
    devices/channels/attributes are extracted with the right ids/values; a
    `<context>`-less or malformed document returns `null`.
  - `ContextXmlViewer.test.tsx` — with a mocked `useArtifactRaw`: the Tree view
    shows a device id; expanding the device reveals a channel; expanding the
    channel reveals an attribute name/value; the Raw toggle shows the source
    text; the download link targets `/api/v1/artifacts/{id}/raw` with the
    filename.

## Error handling / edge cases

- Raw fetch pending → "Loading context…"; error → inline error with the download
  link still available.
- `parseContext` failure / non-context XML → notice + raw fallback.
- Multiple context artifacts on a run or case → one viewer each.

## Limitations

`detect_kind` only sees the first 512 bytes; the `<!DOCTYPE context` marker sits
at the top of the file, well within that window, so detection is reliable.
