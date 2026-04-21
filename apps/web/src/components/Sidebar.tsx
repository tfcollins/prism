import { Box, Stack, Text } from '@chakra-ui/react';
import { Link, NavLink, useParams } from 'react-router-dom';

import { useProjects } from '../api/queries';
import { Logo } from './Logo';

const PRIMARY_NAV = [
  { to: '/projects', label: 'Projects', end: true },
  { to: '/compare', label: 'Compare', end: true },
];

const linkStyle = ({ isActive }: { isActive: boolean }) => ({
  display: 'block',
  padding: '6px 10px',
  borderRadius: '6px',
  fontSize: '13px',
  color: isActive ? '#fff' : '#a0aec0',
  background: isActive ? '#2d3748' : 'transparent',
  textDecoration: 'none',
});

export function Sidebar() {
  const projects = useProjects();
  const { slug: activeSlug } = useParams<{ slug?: string }>();

  return (
    <Box
      as="nav"
      w="220px"
      bg="#171923"
      borderRightWidth={1}
      borderRightColor="#2d3748"
      px={4}
      py={5}
      overflowY="auto"
    >
      <Box mb={6} px={1}>
        <Link to="/projects" aria-label="Prism home">
          <Logo size="sm" />
        </Link>
      </Box>

      <Stack gap={1}>
        {PRIMARY_NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end} style={linkStyle}>
            {item.label}
          </NavLink>
        ))}
      </Stack>

      {projects.data && projects.data.length > 0 && (
        <Box mt={6}>
          <Text fontSize="10px" textTransform="uppercase" letterSpacing="1px" color="#4a5568" mb={2} px={2}>
            Projects
          </Text>
          <Stack gap={1}>
            {projects.data.map((p) => (
              <NavLink
                key={p.id}
                to={`/projects/${p.slug}`}
                style={() => linkStyle({ isActive: p.slug === activeSlug })}
              >
                {p.slug}
              </NavLink>
            ))}
          </Stack>
        </Box>
      )}

      <Text mt={8} fontSize="xs" color="#4a5568" textTransform="uppercase">
        v0.4
      </Text>
    </Box>
  );
}
