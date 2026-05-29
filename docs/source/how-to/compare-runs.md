# Compare runs and overlay signals

Prism's **Compare** view puts two or more runs side by side: a per-case
pass/fail matrix plus the ability to overlay their waveforms or FFTs on a single
plot. This is the payoff for storing signal data — you can *see* a regression,
not just read that a number moved.

## Select runs to compare

From a project dashboard, select two or more runs and choose **Compare**, or
navigate directly with the run IDs:

```text
/compare?runs=<run-id-a>,<run-id-b>
```

The Compare page lists every case across the selected runs with its status in
each, and a headline **pass-rate delta**:

```{image} ../_static/img/screenshots/compare.png
:alt: The Compare view showing two dsp runs with a per-case pass/fail matrix
:class: prism-shot
:align: center
```

## Overlay a signal

For any case backed by a waveform, click **click to overlay** in the Overlay
column. Prism fetches each run's artifact and draws them on one set of axes, so
amplitude or spectral differences line up directly. The same works on the FFT
view to compare frequency content across runs.

:::{tip}
Overlays are most useful between a known-good baseline (for example
`dsp-nightly-41`) and a candidate (`dsp-pr-17`): a shifted resonance or a
raised noise floor jumps out immediately.
:::

## Behind the scenes

Comparison data comes from a single `POST /api/v1/compare` call with the
selected run IDs; overlays reuse the per-artifact
`GET /api/v1/artifacts/{id}/waveform` and `…/fft` endpoints, so an overlaid
trace is computed exactly the same way as a single-run plot. See
{doc}`../reference/rest-api`.
