import { describe, expect, it } from 'vitest';

import { parseContext } from './iioContext';

const CTX = `<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE context [<!ELEMENT context (device)*>]>
<context name="local" description="Emulated Context">
  <context-attribute name="local,kernel" value="5.10.0"/>
  <device id="iio:device0" name="ad7291">
    <attribute name="waiting_for_supplier" value="0"/>
    <channel id="voltage0" type="input">
      <attribute name="raw" value="2048"/>
      <attribute name="scale" value="0.610351562"/>
    </channel>
    <channel id="temp0" type="input" name="temp"/>
  </device>
</context>`;

describe('parseContext', () => {
  it('extracts context metadata and context-level attributes', () => {
    const c = parseContext(CTX)!;
    expect(c.name).toBe('local');
    expect(c.description).toBe('Emulated Context');
    expect(c.contextAttributes).toEqual([{ name: 'local,kernel', value: '5.10.0' }]);
  });

  it('extracts devices with their direct attributes (not channel attrs) and channels', () => {
    const d = parseContext(CTX)!.devices[0];
    expect(parseContext(CTX)!.devices).toHaveLength(1);
    expect(d.id).toBe('iio:device0');
    expect(d.name).toBe('ad7291');
    expect(d.attributes).toEqual([{ name: 'waiting_for_supplier', value: '0' }]);
    expect(d.channels).toHaveLength(2);
  });

  it('extracts channels with id/type/optional name and their attributes', () => {
    const d = parseContext(CTX)!.devices[0];
    expect(d.channels[0]).toMatchObject({ id: 'voltage0', type: 'input', name: null });
    expect(d.channels[0].attributes).toEqual([
      { name: 'raw', value: '2048' },
      { name: 'scale', value: '0.610351562' },
    ]);
    expect(d.channels[1].name).toBe('temp');
  });

  it('returns null for non-context or malformed XML', () => {
    expect(parseContext('<?xml version="1.0"?><testsuites/>')).toBeNull();
    expect(parseContext('not xml <<<')).toBeNull();
  });
});
