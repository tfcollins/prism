# Analyze distortion with genalyzer markers

On a waveform case's **FFT** tab, toggle **genalyzer markers** to overlay a
data-converter analysis computed with the ADI
[genalyzer](https://github.com/analogdevicesinc/genalyzer) library. The markers
label the fundamental, its harmonics (HD2–HD*n*), DC, and the worst spur on the
spectrum, and a panel reports the standard converter metrics — **SNR**, **SFDR**,
**SINAD**, **THD**, and **ENOB**.

```{image} ../_static/img/screenshots/genalyzer.png
:alt: The FFT tab with genalyzer markers overlaid on a harmonically-distorted tone, plus the SNR/SFDR/SINAD/THD/ENOB panel
:class: prism-shot
:align: center
```

The example above is the `harmonic_distortion` demo case: a 1 kHz tone with
deliberate harmonics, so HD2/HD3/HD5 stand clearly above the noise floor and the
SFDR (~40 dB) and THD (~−39 dBc) are dominated by the distortion.

## Tuning the analysis

Two controls sit next to the toggle:

- **Harmonics** — how many harmonics to locate and fold into THD (1–10).
- **Window** — the FFT window: **Blackman-Harris** (the default; robust for
  arbitrary captures), **Hann**, or **None**. `None` skips windowing and is only
  meaningful for *coherently sampled* captures — on a non-coherent capture the
  spectral leakage collapses the reported SNR.

Each `(harmonics, window)` result is cached server-side, so re-opening a
combination you've already computed is instant.

Endpoint: `GET /api/v1/artifacts/{id}/genalyzer?harmonics=N&window=W`.

```{note}
The marker magnitudes are genalyzer dBFS values; the overlaid curve is Prism's
own Welch FFT, so a marker may sit slightly off the trace. The labels and the
metrics panel are the authoritative readout.
```
