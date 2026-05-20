import { Box, Flex, Text } from '@chakra-ui/react';
import { Link, useLocation } from 'react-router-dom';

import { useProjects, useRun } from '../api/queries';

function Sep() {
  return (
    <Text mx={2} color="var(--prism-text-faint)" fontSize="sm">
      /
    </Text>
  );
}

function Crumb({ children, to }: { children: React.ReactNode; to?: string }) {
  if (to) {
    return (
      <Link
        to={to}
        style={{ color: 'var(--prism-text-subtle)', fontSize: '13px', textDecoration: 'none' }}
      >
        {children}
      </Link>
    );
  }
  return (
    <Text fontSize="sm" color="var(--prism-text)" fontWeight="500">
      {children}
    </Text>
  );
}

function ProjectsCrumb() {
  return <Crumb to="/projects">Projects</Crumb>;
}

function ProjectCrumb({ slug }: { slug: string }) {
  return (
    <Flex align="center">
      <ProjectsCrumb />
      <Sep />
      <Crumb>{slug}</Crumb>
    </Flex>
  );
}

function RunCrumb({ runId }: { runId: string }) {
  const run = useRun(runId);
  const projects = useProjects();
  const projectSlug = projects.data?.find((p) => p.id === run.data?.project_id)?.slug;

  return (
    <Flex align="center">
      <ProjectsCrumb />
      <Sep />
      {projectSlug ? (
        <Crumb to={`/projects/${projectSlug}`}>{projectSlug}</Crumb>
      ) : (
        <Crumb>…</Crumb>
      )}
      <Sep />
      <Crumb>{run.data?.name ?? '…'}</Crumb>
    </Flex>
  );
}

export function Breadcrumbs() {
  const { pathname } = useLocation();
  const segments = pathname.split('/').filter(Boolean);

  if (segments.length === 0 || segments[0] === 'projects') {
    if (segments.length >= 2) return <ProjectCrumb slug={segments[1]} />;
    return (
      <Flex align="center">
        <Crumb>Projects</Crumb>
      </Flex>
    );
  }
  if (segments[0] === 'runs' && segments.length >= 2) {
    return <RunCrumb runId={segments[1]} />;
  }
  if (segments[0] === 'compare') {
    return (
      <Flex align="center">
        <Crumb>Compare</Crumb>
      </Flex>
    );
  }
  return <Box />;
}
