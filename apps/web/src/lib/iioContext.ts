// Parser for libiio context XML dumps (e.g. pyadi-iio emulated devices).
//
// Turns the raw XML into a structured tree so the viewer can render an
// expandable device → channel → attribute hierarchy. Returns null for non-context
// or malformed XML so the viewer can fall back to the raw view.

export interface CtxAttr {
  name: string;
  value: string;
}

export interface CtxChannel {
  id: string;
  type: string;
  name: string | null;
  attributes: CtxAttr[];
}

export interface CtxDevice {
  id: string;
  name: string | null;
  attributes: CtxAttr[];
  channels: CtxChannel[];
}

export interface ParsedContext {
  name: string | null;
  description: string | null;
  contextAttributes: CtxAttr[];
  devices: CtxDevice[];
}

// Note: traverse via `.children` / `.localName` rather than CSS `:scope >`
// selectors — jsdom's selector engine rejects `:scope` in some versions, and
// element ids like `iio:device0` break naive selector building.
function childrenByTag(el: Element, tag: string): Element[] {
  return Array.from(el.children).filter((c) => c.localName === tag);
}

/** Read `<attribute name= value=>` from the direct children of an element. */
function directAttributes(el: Element): CtxAttr[] {
  return childrenByTag(el, 'attribute').map((a) => ({
    name: a.getAttribute('name') ?? '',
    value: a.getAttribute('value') ?? '',
  }));
}

export function parseContext(xml: string): ParsedContext | null {
  let doc: Document;
  try {
    doc = new DOMParser().parseFromString(xml, 'application/xml');
  } catch {
    return null;
  }
  // DOMParser reports malformed XML via a <parsererror> node rather than throwing.
  if (doc.getElementsByTagName('parsererror').length > 0) return null;

  const context = doc.documentElement;
  if (!context || context.localName !== 'context') return null;

  const devices: CtxDevice[] = childrenByTag(context, 'device').map((d) => ({
    id: d.getAttribute('id') ?? '',
    name: d.getAttribute('name'),
    attributes: directAttributes(d),
    channels: childrenByTag(d, 'channel').map((c) => ({
      id: c.getAttribute('id') ?? '',
      type: c.getAttribute('type') ?? '',
      name: c.getAttribute('name'),
      attributes: directAttributes(c),
    })),
  }));

  const contextAttributes: CtxAttr[] = childrenByTag(context, 'context-attribute').map((a) => ({
    name: a.getAttribute('name') ?? '',
    value: a.getAttribute('value') ?? '',
  }));

  return {
    name: context.getAttribute('name'),
    description: context.getAttribute('description'),
    contextAttributes,
    devices,
  };
}
