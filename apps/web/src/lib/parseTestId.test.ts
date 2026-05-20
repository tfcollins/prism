import { describe, expect, it } from 'vitest';

import { parseTestId, summarizeParams } from './parseTestId';

describe('parseTestId', () => {
  it('returns the bare name when there is no parametrize block', () => {
    expect(parseTestId('test_basic')).toEqual({
      baseName: 'test_basic',
      params: [],
      raw: 'test_basic',
    });
  });

  it('parses a simple two-param parametrize id', () => {
    const out = parseTestId('test_x[a=1-b=2]');
    expect(out.baseName).toBe('test_x');
    expect(out.params).toEqual([
      { key: 'a', value: '1' },
      { key: 'b', value: '2' },
    ]);
  });

  it('keeps `-` inside a value (negative numbers, dates)', () => {
    const out = parseTestId('test_neg[gain=-20-fs=4000000]');
    expect(out.params).toEqual([
      { key: 'gain', value: '-20' },
      { key: 'fs', value: '4000000' },
    ]);
  });

  it('handles a value that is itself a python-repr dict', () => {
    const out = parseTestId(
      "test_ad9364_sfdr[param_set={'tx_lo': 1000000000, 'tx_hardwaregain_chan0': -20, 'sample_rate': 4000000}-sfdr_min=40-channel=0-classname=adi.ad9364]",
    );
    expect(out.baseName).toBe('test_ad9364_sfdr');
    expect(out.params).toHaveLength(4);
    expect(out.params[0].key).toBe('param_set');
    expect(out.params[0].value).toMatch(/^\{.*\}$/); // a `{...}` dict literal
    expect(out.params[0].value).toContain("'tx_hardwaregain_chan0': -20");
    expect(out.params[1]).toEqual({ key: 'sfdr_min', value: '40' });
    expect(out.params[2]).toEqual({ key: 'channel', value: '0' });
    expect(out.params[3]).toEqual({ key: 'classname', value: 'adi.ad9364' });
  });

  it('preserves the raw input', () => {
    const raw = 'test_x[a=1-b=2]';
    expect(parseTestId(raw).raw).toBe(raw);
  });

  it('returns empty params when the parametrize bracket has no key= form', () => {
    // pytest can also produce numeric-only ids like `test_x[0]` if the user
    // supplies `ids=` explicitly. We treat that as one param with key=''
    // is wrong; better: return no params and keep the bracket in raw.
    const out = parseTestId('test_x[0]');
    expect(out.baseName).toBe('test_x');
    expect(out.params).toEqual([]);
  });
});

describe('summarizeParams', () => {
  it('joins key=value pairs with `·` and skips classname', () => {
    const summary = summarizeParams([
      { key: 'sfdr_min', value: '40' },
      { key: 'channel', value: '0' },
      { key: 'classname', value: 'adi.ad9364' },
    ]);
    expect(summary).toBe('sfdr_min=40 · channel=0');
  });

  it('truncates long values with an ellipsis', () => {
    const summary = summarizeParams([{ key: 'param_set', value: 'a'.repeat(100) }]);
    expect(summary.length).toBeLessThanOrEqual(80);
    expect(summary).toContain('…');
  });

  it('returns "" when nothing is visible (only classname)', () => {
    expect(summarizeParams([{ key: 'classname', value: 'foo' }])).toBe('');
  });
});
