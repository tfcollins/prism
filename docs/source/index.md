(home)=

# Prism

```{image} _static/img/screenshots/dashboard.png
:alt: The Prism project dashboard showing a runs table with pass/fail status, suites and tag filters
:class: prism-shot
:align: center
```

**Prism** is a self-hostable web app for managing, browsing, plotting, and
cross-analysing test results — JUnit XML pass/fail metadata *plus* the
measurement artifacts your tests produce (waveforms, FFTs, spectra, logs).

When a test suite emits *both* pass/fail outcomes and signal data — DSP
pipelines, RF benches, audio codecs — most CI dashboards drop the signal data
on the floor. Prism stores it, lets you browse it, and overlays it across runs.

## The documentation, by what you need

This documentation follows the [Diátaxis](https://diataxis.fr/) framework. Pick
the quadrant that matches what you're trying to do:

::::{grid}
:columns: 2

:::{card} 🎓 Tutorials
:ref: tutorials-index

Learning-oriented. Start here if you're new — stand up the stack, upload your
first run, and see a waveform plot.
:::

:::{card} 🛠️ How-to guides
:ref: how-to-index

Task-oriented recipes: wire Prism into CI, record measurements from pytest,
compare runs, and upload over raw HTTP.
:::

:::{card} 📖 Reference
:ref: reference-index

Information-oriented. The REST API, the data model, file-naming conventions,
and the `upload_run.py` flag/exit-code tables.
:::

:::{card} 💡 Explanation
:ref: explanation-index

Understanding-oriented. How ingest works, why artifacts are content-addressed,
and the overall architecture.
:::

::::

## Quickstart

```bash
git clone <repo> && cd prism
cp deploy/.env.example deploy/.env
# edit deploy/.env: set JWT_SECRET (≥32 chars) and ADMIN_PASSWORD
make up
open http://localhost:8180
```

Then follow the [getting-started tutorial](tutorials/getting-started.md) to
upload your first run.

```{toctree}
:hidden:
:caption: Documentation

tutorials/index
how-to/index
reference/index
explanation/index
```
