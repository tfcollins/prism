import { Box, Button, Flex, Input, Stack, Text } from '@chakra-ui/react';
import { useState } from 'react';

import { useAddRunTag, useDeleteRunTag, useUpdateRunTag } from '../api/queries';
import type { RunTag } from '../api/types';

function TagRow({ runId, tag }: { runId: string; tag: RunTag }) {
  const update = useUpdateRunTag(runId);
  const del = useDeleteRunTag(runId);
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(tag.value);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = () => {
    setError(null);
    update.mutate(
      { key: tag.key, value },
      {
        onSuccess: () => setEditing(false),
        onError: () => setError('Could not update tag (it may no longer exist).'),
      },
    );
  };

  return (
    <Flex align="center" gap={2} wrap="wrap">
      <Text fontFamily="mono" fontSize="sm" fontWeight="600">
        {tag.key}
      </Text>
      <Text fontSize="sm">=</Text>
      {editing ? (
        <>
          <Input
            size="xs"
            maxW="180px"
            maxLength={500}
            aria-label={`edit value for ${tag.key}`}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <Button
            size="xs"
            colorPalette="blue"
            loading={update.isPending}
            aria-label={`Save ${tag.key}`}
            onClick={save}
          >
            Save
          </Button>
          <Button
            size="xs"
            variant="ghost"
            aria-label={`Cancel ${tag.key}`}
            onClick={() => {
              setEditing(false);
              setValue(tag.value);
              setError(null);
            }}
          >
            Cancel
          </Button>
        </>
      ) : (
        <>
          <Text fontFamily="mono" fontSize="sm">
            {tag.value}
          </Text>
          <Button
            size="xs"
            variant="outline"
            aria-label={`Edit ${tag.key}`}
            onClick={() => {
              setValue(tag.value);
              setEditing(true);
            }}
          >
            Edit
          </Button>
          {confirmDelete ? (
            <Button
              size="xs"
              colorPalette="red"
              loading={del.isPending}
              aria-label={`Confirm delete ${tag.key}`}
              onClick={() =>
                del.mutate(tag.key, {
                  onError: () => setError('Could not delete tag.'),
                })
              }
            >
              Confirm delete
            </Button>
          ) : (
            <Button
              size="xs"
              variant="ghost"
              aria-label={`Delete ${tag.key}`}
              onClick={() => setConfirmDelete(true)}
            >
              ✕
            </Button>
          )}
        </>
      )}
      {error && (
        <Text fontSize="xs" color="red.400">
          {error}
        </Text>
      )}
    </Flex>
  );
}

export function TagsEditor({ runId, tags }: { runId: string; tags: RunTag[] }) {
  const add = useAddRunTag(runId);
  const [key, setKey] = useState('');
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    if (!key.trim() || !value.trim()) return;
    add.mutate(
      { key: key.trim(), value: value.trim() },
      {
        onSuccess: () => {
          setKey('');
          setValue('');
        },
        onError: (e: unknown) => {
          const status = (e as { response?: { status?: number } })?.response?.status;
          setError(
            status === 409 ? 'Tag already exists — edit it instead.' : 'Could not add tag.',
          );
        },
      },
    );
  };

  return (
    <Stack gap={2}>
      {tags.length === 0 ? (
        <Text fontSize="xs" color="var(--prism-text-faint)">
          none
        </Text>
      ) : (
        tags.map((t) => <TagRow key={t.key} runId={runId} tag={t} />)
      )}
      <Flex align="center" gap={2} wrap="wrap" mt={1}>
        <Input
          size="xs"
          maxW="140px"
          maxLength={100}
          placeholder="key"
          aria-label="new tag key"
          value={key}
          onChange={(e) => setKey(e.target.value)}
        />
        <Input
          size="xs"
          maxW="180px"
          maxLength={500}
          placeholder="value"
          aria-label="new tag value"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <Button
          size="xs"
          colorPalette="blue"
          loading={add.isPending}
          aria-label="Add tag"
          onClick={submit}
        >
          Add tag
        </Button>
      </Flex>
      {error && (
        <Box>
          <Text fontSize="xs" color="red.400">
            {error}
          </Text>
        </Box>
      )}
    </Stack>
  );
}
