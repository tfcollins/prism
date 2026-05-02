import { describe, expect, it } from 'vitest';

import type { CaseArtifact } from '../src/api/types';
import { INLINE_RENDERABLE_KINDS, pickInlineArtifact } from '../src/lib/inlineKinds';

function fakeArtifact(overrides: Partial<CaseArtifact>): CaseArtifact {
  return {
    id: 'a1',
    kind: 'log_text',
    manifest_kind: null,
    filename: 'thing.html',
    size_bytes: 0,
    ...overrides,
  };
}

describe('pickInlineArtifact', () => {
  it('returns undefined when manifest_kind is null', () => {
    const got = pickInlineArtifact([fakeArtifact({ manifest_kind: null })]);
    expect(got).toBeUndefined();
  });

  it('returns undefined when manifest_kind is unknown', () => {
    const got = pickInlineArtifact([fakeArtifact({ manifest_kind: 'unknown.thing' })]);
    expect(got).toBeUndefined();
  });

  it('returns undefined when filename is not .html', () => {
    const got = pickInlineArtifact([
      fakeArtifact({ manifest_kind: 'adi.iq', filename: 'spectrum.json' }),
    ]);
    expect(got).toBeUndefined();
  });

  it('returns the matching artifact for adi.iq + .html', () => {
    const a = fakeArtifact({ manifest_kind: 'adi.iq', filename: 'spectrum.html' });
    const got = pickInlineArtifact([a]);
    expect(got).toBe(a);
  });

  it('matches case-insensitively on the .html extension', () => {
    const a = fakeArtifact({ manifest_kind: 'adi.iq', filename: 'spectrum.HTML' });
    const got = pickInlineArtifact([a]);
    expect(got).toBe(a);
  });

  it('exposes the kinds set for documentation/extension purposes', () => {
    expect(INLINE_RENDERABLE_KINDS.has('adi.iq')).toBe(true);
    expect(INLINE_RENDERABLE_KINDS.has('adi.devicetree')).toBe(true);
    expect(INLINE_RENDERABLE_KINDS.has('adi.jesd_clock')).toBe(true);
  });
});
