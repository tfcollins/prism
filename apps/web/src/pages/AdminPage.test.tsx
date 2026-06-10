import { ChakraProvider } from '@chakra-ui/react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { system } from '../theme';

const mutate = vi.fn();

vi.mock('../api/queries', () => ({
  useAdminAccounts: () => ({ isLoading: false, data: [] }),
  useAdminActivity: () => ({ isLoading: false, data: [] }),
  useAdminBackups: () => ({ isLoading: false, data: [] }),
  useAdminLogs: () => ({ isLoading: false, data: { available: false, message: 'x', lines: [] } }),
  useAdminProjects: () => ({
    isLoading: false,
    data: [{ id: '1', slug: 'audio', name: 'Audio', run_count: 7 }],
  }),
  useDeleteProject: () => ({ mutate, isPending: false }),
  useMatrixConfig: () => ({ isLoading: false, data: undefined }),
  useUpsertMatrixConfig: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));
import { ProjectsTab } from './AdminPage';

function renderTab() {
  return render(
    <ChakraProvider value={system}>
      <ProjectsTab />
    </ChakraProvider>,
  );
}

describe('AdminPage projects delete', () => {
  it('requires typing the slug before the delete is armed, then deletes', () => {
    renderTab();

    // project row visible with run count
    expect(screen.getByText('audio')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();

    // arm the confirmation
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const confirm = screen.getByRole('button', { name: 'Confirm delete' });
    expect(confirm).toBeDisabled();

    // wrong text keeps it disabled
    const input = screen.getByLabelText('Confirm slug for audio');
    fireEvent.change(input, { target: { value: 'aud' } });
    expect(confirm).toBeDisabled();

    // exact slug arms it
    fireEvent.change(input, { target: { value: 'audio' } });
    expect(confirm).toBeEnabled();

    fireEvent.click(confirm);
    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toBe('audio');
  });
});
