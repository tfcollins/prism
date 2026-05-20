import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { CopyButton } from '../src/components/CopyButton';

function renderCopy(value: string, label?: string) {
  return render(
    <ChakraProvider value={defaultSystem}>
      <CopyButton value={value} label={label} />
    </ChakraProvider>,
  );
}

describe('CopyButton', () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  it('writes the value to the clipboard and confirms', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    renderCopy('run-123', 'copy id');
    const btn = screen.getByText('copy id');
    fireEvent.click(btn);

    expect(writeText).toHaveBeenCalledWith('run-123');
    await waitFor(() => expect(screen.getByText('✓ copied')).toBeInTheDocument());
  });

  it('does not throw when the clipboard API rejects', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('insecure context'));
    Object.assign(navigator, { clipboard: { writeText } });

    renderCopy('x');
    fireEvent.click(screen.getByText('copy'));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    // stays on the default label — no confirmation, no crash
    expect(screen.getByText('copy')).toBeInTheDocument();
  });
});
