import { Box, Button, Heading, Input, Stack, Table, Text } from '@chakra-ui/react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { api } from '../api/client';
import type { CreateProjectRequest, Project } from '../api/types';

export function ProjectsPage() {
  const qc = useQueryClient();
  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: async () => (await api.get<Project[]>('/projects')).data,
  });

  const [slug, setSlug] = useState('');
  const [name, setName] = useState('');

  const createMutation = useMutation({
    mutationFn: async (body: CreateProjectRequest) => {
      const res = await api.post<Project>('/projects', body);
      return res.data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['projects'] });
      setSlug('');
      setName('');
    },
  });

  return (
    <Box p={8}>
      <Heading size="xl" mb={6}>
        Projects
      </Heading>

      <Stack
        as="form"
        gap={2}
        direction={{ base: 'column', md: 'row' }}
        mb={6}
        onSubmit={(e) => {
          e.preventDefault();
          createMutation.mutate({ slug, name });
        }}
      >
        <Input placeholder="slug (e.g. audio-codec)" value={slug} onChange={(e) => setSlug(e.target.value)} />
        <Input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
        <Button type="submit" colorPalette="blue" loading={createMutation.isPending}>
          Create
        </Button>
      </Stack>
      {createMutation.isError && (
        <Text color="red.400" mb={4}>
          Could not create project — slug may already exist or be invalid.
        </Text>
      )}

      {projectsQuery.isLoading && <Text>Loading…</Text>}
      {projectsQuery.data && projectsQuery.data.length === 0 && (
        <Text color="gray.500">No projects yet.</Text>
      )}
      {projectsQuery.data && projectsQuery.data.length > 0 && (
        <Table.Root variant="outline">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader>Slug</Table.ColumnHeader>
              <Table.ColumnHeader>Name</Table.ColumnHeader>
              <Table.ColumnHeader>Description</Table.ColumnHeader>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {projectsQuery.data.map((p) => (
              <Table.Row key={p.id}>
                <Table.Cell>{p.slug}</Table.Cell>
                <Table.Cell>{p.name}</Table.Cell>
                <Table.Cell>{p.description}</Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      )}
    </Box>
  );
}
