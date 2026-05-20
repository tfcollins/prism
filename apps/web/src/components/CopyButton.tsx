import { Box } from '@chakra-ui/react';
import { useState } from 'react';

/**
 * Inline copy-to-clipboard affordance with transient confirmation. Self-contained
 * (no global toaster) so it can sit next to any UUID / URL an engineer might paste
 * into Slack or Jira.
 */
export function CopyButton({ value, label = 'copy' }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable (e.g. insecure context) — silently no-op
    }
  };

  return (
    <Box
      as="button"
      onClick={copy}
      px={2}
      py="1px"
      borderRadius="sm"
      borderWidth={1}
      fontSize="xs"
      fontFamily="mono"
      cursor="pointer"
      bg="var(--prism-bg-surface)"
      color={copied ? 'var(--prism-status-pass-fg)' : 'var(--prism-text-muted)'}
      borderColor="var(--prism-border)"
      title={`Copy: ${value}`}
    >
      {copied ? '✓ copied' : label}
    </Box>
  );
}
