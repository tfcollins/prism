import { Badge, Box, Heading, Stack, Text } from '@chakra-ui/react';
import { Link as RouterLink, useSearchParams } from 'react-router-dom';

import { useSearch } from '../api/queries';
import type { SearchHit } from '../api/types';
import { AppShell } from '../components/AppShell';

const KIND_LABEL: Record<SearchHit['kind'], string> = {
  project: 'Projects',
  run: 'Runs',
  case: 'Test cases',
  commit: 'Commits',
};

const KIND_ORDER: SearchHit['kind'][] = ['project', 'run', 'case', 'commit'];

const KIND_COLOR: Record<SearchHit['kind'], string> = {
  project: 'purple',
  run: 'blue',
  case: 'orange',
  commit: 'teal',
};

function hitTarget(hit: SearchHit): string {
  if (hit.run_id) return `/runs/${hit.run_id}`;
  if (hit.project_slug) return `/projects/${hit.project_slug}`;
  return '/';
}

export function SearchResultsPage() {
  const [params] = useSearchParams();
  const query = (params.get('q') ?? '').trim();
  const { data, isLoading, isError } = useSearch(query);

  const grouped = KIND_ORDER.map((kind) => ({
    kind,
    hits: (data ?? []).filter((h) => h.kind === kind),
  })).filter((g) => g.hits.length > 0);

  return (
    <AppShell>
      <Heading size="lg" mb={1}>
        Search
      </Heading>
      <Text color="var(--prism-text-subtle)" mb={4}>
        {query.length >= 2 ? `Results for “${query}”` : 'Type at least two characters to search.'}
      </Text>

      {query.length >= 2 && isLoading && <Text>Searching…</Text>}
      {isError && <Text color="red.500">Search failed. Please try again.</Text>}
      {query.length >= 2 && !isLoading && !isError && grouped.length === 0 && (
        <Text color="var(--prism-text-subtle)">No matches found.</Text>
      )}

      <Stack gap={6}>
        {grouped.map((group) => (
          <Box key={group.kind}>
            <Heading size="sm" mb={2} color="var(--prism-text-subtle)">
              {KIND_LABEL[group.kind]} ({group.hits.length})
            </Heading>
            <Stack gap={1}>
              {group.hits.map((hit, i) => (
                <Box
                  key={`${hit.kind}-${hit.run_id ?? hit.project_slug ?? ''}-${i}`}
                  asChild
                  px={3}
                  py={2}
                  borderWidth={1}
                  borderColor="var(--prism-border)"
                  borderRadius="md"
                  _hover={{ bg: 'var(--prism-bg-hover)' }}
                >
                  <RouterLink to={hitTarget(hit)}>
                    <Badge colorPalette={KIND_COLOR[hit.kind]} mr={2}>
                      {hit.kind}
                    </Badge>
                    <Text as="span" fontWeight="medium">
                      {hit.title}
                    </Text>
                    {hit.subtitle && (
                      <Text as="span" color="var(--prism-text-subtle)" ml={2} fontSize="sm">
                        {hit.subtitle}
                      </Text>
                    )}
                  </RouterLink>
                </Box>
              ))}
            </Stack>
          </Box>
        ))}
      </Stack>
    </AppShell>
  );
}
