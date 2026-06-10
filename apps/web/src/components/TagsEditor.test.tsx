import { ChakraProvider } from '@chakra-ui/react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { RunTag } from '../api/types';
import { system } from '../theme';

const addMutate = vi.fn();
const updateMutate = vi.fn();
const deleteMutate = vi.fn();

vi.mock('../api/queries', () => ({
  useAddRunTag: () => ({ mutate: addMutate, isPending: false, isError: false }),
  useUpdateRunTag: () => ({ mutate: updateMutate, isPending: false, isError: false }),
  useDeleteRunTag: () => ({ mutate: deleteMutate, isPending: false, isError: false }),
}));

import { TagsEditor } from './TagsEditor';

const TAGS: RunTag[] = [{ key: 'hw', value: 'ad9081' }];

function renderEditor(tags: RunTag[] = TAGS) {
  return render(
    <ChakraProvider value={system}>
      <TagsEditor runId="r1" tags={tags} />
    </ChakraProvider>,
  );
}

describe('TagsEditor', () => {
  it('renders existing tags', () => {
    renderEditor();
    expect(screen.getByText('hw')).toBeInTheDocument();
    expect(screen.getByText('ad9081')).toBeInTheDocument();
  });

  it('adds a tag', () => {
    renderEditor([]);
    fireEvent.change(screen.getByLabelText('new tag key'), { target: { value: 'platform' } });
    fireEvent.change(screen.getByLabelText('new tag value'), { target: { value: 'zcu102' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add tag' }));
    expect(addMutate).toHaveBeenCalledWith(
      { key: 'platform', value: 'zcu102' },
      expect.anything(),
    );
  });

  it('edits a tag value', () => {
    renderEditor();
    fireEvent.click(screen.getByRole('button', { name: 'Edit hw' }));
    fireEvent.change(screen.getByLabelText('edit value for hw'), { target: { value: 'adrv9009' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save hw' }));
    expect(updateMutate).toHaveBeenCalledWith(
      { key: 'hw', value: 'adrv9009' },
      expect.anything(),
    );
  });

  it('deletes a tag after confirm', () => {
    renderEditor();
    fireEvent.click(screen.getByRole('button', { name: 'Delete hw' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm delete hw' }));
    expect(deleteMutate).toHaveBeenCalledWith('hw', expect.anything());
  });
});
