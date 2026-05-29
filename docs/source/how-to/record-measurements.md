# Record numeric measurements from tests

A **measurement** is a named numeric value attached to a test case — channel
power, ACPR, SNR, and so on. Emit them straight from your test body and they
flow into the JUnit `<properties>` and become first-class Prism measurements
with pass/fail margins, no extra upload step.

## With `pytest-prism`

The `pytest-prism` plugin ships a `record_measurement()` helper:

```python
from pytest_prism import record_measurement

def test_acpr():
    record_measurement("channel_power_dBm", -10.2, unit="dBm", spec_max=-9.0)
    record_measurement("acpr_dBc", -45.3, unit="dBc", spec_max=-40.0)
```

## With plain pytest

No plugin required — `record_property` plus the optional `__unit` / `__min` /
`__max` siblings follow the same convention:

```python
def test_acpr(record_property):
    record_property("channel_power_dBm", -10.2)
    record_property("channel_power_dBm__unit", "dBm")
    record_property("channel_power_dBm__max", -9.0)
```

## Without pytest

For non-pytest CI, `upload_run.py --measurement` injects the same properties
into a single-testcase JUnit:

```bash
python3 scripts/upload_run.py results.xml \
  --measurement channel_power_dBm=-10.2:dBm::-9.0 \
  --wait
```

The format is `name=value[:unit[:min[:max]]]`.

## How limits and margins work

Spec limits (`spec_min` / `spec_max`) are optional. Prism derives pass/fail and
the **margin** (the signed distance to the nearest limit) *at read time* rather
than storing them — so re-speccing a project never requires rewriting
historical rows. See {doc}`../explanation/design` for the reasoning, and
{doc}`../reference/data-model` for the measurement schema.
