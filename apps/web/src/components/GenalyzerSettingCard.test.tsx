import { ChakraProvider } from '@chakra-ui/react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { system } from '../theme';

const mutate = vi.fn();
let mockUser: { is_admin?: boolean } | null = { is_admin: true };
let mockProject: { genalyzer_auto: boolean } = { genalyzer_auto: false };

vi.mock('../api/queries', () => ({
  useProject: () => ({ data: mockProject }),
  useUpdateProject: () => ({ mutate, isPending: false }),
}));
vi.mock('../auth/useAuth', () => ({ useAuth: () => ({ user: mockUser }) }));

import { GenalyzerSettingCard } from './GenalyzerSettingCard';

function renderCard() {
  return render(
    <ChakraProvider value={system}>
      <GenalyzerSettingCard slug="audio" />
    </ChakraProvider>,
  );
}

beforeEach(() => {
  mutate.mockClear();
  mockUser = { is_admin: true };
  mockProject = { genalyzer_auto: false };
});

describe('GenalyzerSettingCard', () => {
  it('enables when off (admin)', () => {
    renderCard();
    const btn = screen.getByRole('button', { name: /enable/i });
    fireEvent.click(btn);
    expect(mutate).toHaveBeenCalledWith({ genalyzer_auto: true });
  });

  it('disables when on', () => {
    mockProject = { genalyzer_auto: true };
    renderCard();
    fireEvent.click(screen.getByRole('button', { name: /disable/i }));
    expect(mutate).toHaveBeenCalledWith({ genalyzer_auto: false });
  });

  it('renders nothing for non-admins', () => {
    mockUser = { is_admin: false };
    const { container } = renderCard();
    expect(container).toBeEmptyDOMElement();
  });
});
