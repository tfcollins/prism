# File & upload conventions

## One JUnit upload = one Test Suite Run

A project contains many **Test Suite Runs**. Each run is one JUnit XML upload
that should contain exactly **one** `<testsuite>` element:

```xml
<?xml version="1.0"?>
<testsuites>
  <testsuite name="dsp" tests="3" failures="1" time="0.36">
    <testcase classname="codec" name="sine_sweep_1khz" time="0.12"/>
    <testcase classname="codec" name="sine_sweep_5khz" time="0.14">
      <failure message="SNR regression">…</failure>
    </testcase>
    <testcase classname="latency" name="impulse_response" time="0.10"/>
  </testsuite>
</testsuites>
```

The dashboard's **Suite** column shows that single suite name at a glance, and
the run-detail page flattens the case list. Uploads with multiple `<testsuite>`
elements are still accepted (they render as an expandable tree), but
one-suite-per-upload is the recommended shape.

## Archive file naming

Files inside the optional upload archive follow
`{suite}__{case}__{label}.{ext}` (double underscores between segments). The
parser uses this to attach each file to the right run / suite / case:

| Filename | Attaches to |
|---|---|
| `dsp__sine_sweep_1khz__waveform.csv` | suite `dsp`, case `sine_sweep_1khz` |
| `dsp__suite-log.log` | suite `dsp` |
| `readme.log` | the run |

## Supported artifact types

| Extension(s) | Kind |
|---|---|
| `*.xml` | JUnit |
| `*.csv`, `*.npy`, `*.h5` | waveform |
| `*.csv` (freq,power), `*.s1p`, `*.s2p` | spectrum |
| `*.wav` | audio |
| `*.png` | image |
| `*.log` | log |
| anything else | `other_binary` |

## Waveform CSV format

A single column of floats, optionally with a `# sample_rate=<int>` comment on
the first line:

```text
# sample_rate=48000
0.000000
0.130526
0.258819
...
```
