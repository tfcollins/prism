import type { CaseArtifact } from '../api/types';

/**
 * manifest_kinds whose primary artifact is HTML safe to render inline as an iframe.
 *
 * Consumer-defined kinds (declared by pytest-prism Renderer subclasses); namespaced
 * by package (`adi.*` from pyadi-iio + sister repos). Add new kinds here when they
 * onboard.
 */
export const INLINE_RENDERABLE_KINDS = new Set<string>([
  'adi.iq',
  'adi.devicetree',
  'adi.jesd_clock',
]);

/**
 * Pick an artifact suitable for inline iframe rendering: matching manifest_kind and
 * an .html filename. Returns undefined if no candidate exists.
 */
export function pickInlineArtifact(
  artifacts: ReadonlyArray<CaseArtifact>,
): CaseArtifact | undefined {
  return artifacts.find(
    (a) =>
      a.manifest_kind != null &&
      INLINE_RENDERABLE_KINDS.has(a.manifest_kind) &&
      a.filename.toLowerCase().endsWith('.html'),
  );
}
