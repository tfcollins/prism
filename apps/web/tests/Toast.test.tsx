import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Toast } from '../src/components/Toast';

function renderToast(onClose: () => void, durationMs?: number) {
  return render(
    <ChakraProvider value={defaultSystem}>
      <Toast message="Ingest complete: pass" onClose={onClose} durationMs={durationMs} />
    </ChakraProvider>,
  );
}

describe('Toast', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('renders the message', () => {
    renderToast(vi.fn());
    expect(screen.getByText('Ingest complete: pass')).toBeInTheDocument();
  });

  it('auto-dismisses after the duration', () => {
    const onClose = vi.fn();
    renderToast(onClose, 3000);
    expect(onClose).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes when the dismiss button is clicked', () => {
    const onClose = vi.fn();
    renderToast(onClose);
    fireEvent.click(screen.getByText('✕'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
