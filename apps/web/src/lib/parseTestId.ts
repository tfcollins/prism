/**
 * Parse a pytest-style test name into a base function name plus parametrize
 * key/value pairs.
 *
 * Pytest renders a parametrized test as
 *   `test_func[key1=value1-key2=value2-...]`
 * where each pair is separated by `-`. Values may themselves contain `-`
 * (negative numbers, dates, etc.), so we don't blindly split on `-`. Instead
 * we treat a `-` as a parameter separator only when it is immediately
 * followed by `<identifier>=`, which is the shape pytest uses for the next
 * param. The first `<identifier>=` (at offset 0 inside the bracket) is the
 * first parameter regardless.
 */
export interface ParsedTestId {
  baseName: string;
  params: Array<{ key: string; value: string }>;
  raw: string;
}

const KEY_AT_BOUNDARY = /(\w+)=/g;

export function parseTestId(name: string): ParsedTestId {
  const m = /^([^[]+)\[(.*)\]$/s.exec(name);
  if (!m) return { baseName: name, params: [], raw: name };
  const baseName = m[1];
  const inside = m[2];

  const positions: Array<{ idx: number; key: string }> = [];
  let match: RegExpExecArray | null;
  KEY_AT_BOUNDARY.lastIndex = 0;
  while ((match = KEY_AT_BOUNDARY.exec(inside)) !== null) {
    if (match.index === 0 || inside[match.index - 1] === '-') {
      positions.push({ idx: match.index, key: match[1] });
    }
  }

  if (positions.length === 0) {
    return { baseName, params: [], raw: name };
  }

  const params: Array<{ key: string; value: string }> = [];
  for (let i = 0; i < positions.length; i++) {
    const start = positions[i].idx + positions[i].key.length + 1; // skip "key="
    // -1 to drop the `-` separator preceding the next key, when there is one.
    const end = i + 1 < positions.length ? positions[i + 1].idx - 1 : inside.length;
    params.push({ key: positions[i].key, value: inside.slice(start, end) });
  }
  return { baseName, params, raw: name };
}

/**
 * Render a parametrize summary suitable for a sidebar / list label.
 *
 * Skips noisy keys (classname is shown elsewhere) and trims long values
 * with ellipsis so the label fits in narrow rails.
 */
export function summarizeParams(
  params: ReadonlyArray<{ key: string; value: string }>,
  maxLen: number = 80,
): string {
  const visible = params.filter((p) => p.key !== 'classname');
  if (visible.length === 0) return '';
  const pieces = visible.map((p) => {
    const v = p.value.length > 24 ? p.value.slice(0, 21) + '…' : p.value;
    return `${p.key}=${v}`;
  });
  let out = pieces.join(' · ');
  if (out.length > maxLen) out = out.slice(0, maxLen - 1) + '…';
  return out;
}
