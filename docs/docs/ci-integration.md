# Integrating with your CI

## Generic shell

```bash
# After your test suite produces junit.xml, optionally bundle artifacts:
zip -r artifacts.zip waveforms/ logs/

curl -s -c /tmp/p.txt -H 'Content-Type: application/json' \
  -d "{\"email\":\"$PRISM_EMAIL\",\"password\":\"$PRISM_PASSWORD\"}" \
  "$PRISM_URL/api/v1/auth/login"

CSRF=$(awk -F'\t' '/prism_csrf/{print $7}' /tmp/p.txt)

curl -fs -b /tmp/p.txt -H "X-Prism-Csrf: $CSRF" \
  -F "junit=@junit.xml;type=application/xml" \
  -F "archive=@artifacts.zip;type=application/zip" \
  -F "metadata={\"project_slug\":\"$PROJECT\",\"name\":\"$BUILD_ID\",\"tags\":{\"branch\":\"$GIT_BRANCH\",\"sha\":\"$GIT_SHA\"}}" \
  "$PRISM_URL/api/v1/runs"
```

## GitHub Actions example

```yaml
- name: Upload to Prism
  if: always()  # upload even on test failures
  env:
    PRISM_URL: ${{ secrets.PRISM_URL }}
    PRISM_EMAIL: ${{ secrets.PRISM_EMAIL }}
    PRISM_PASSWORD: ${{ secrets.PRISM_PASSWORD }}
  run: ./scripts/upload-to-prism.sh
```

Note: a long-lived Prism user account for CI is the simplest pattern in v1. API tokens are planned for a future release.
