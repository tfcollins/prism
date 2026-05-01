import { Box, IconButton, Stack, Text } from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import { Link, NavLink, useParams } from 'react-router-dom';

import { useProjects } from '../api/queries';
import { Logo } from './Logo';

const PRIMARY_NAV = [
  { to: '/projects', label: 'Projects', short: 'P', end: true },
  { to: '/compare', label: 'Compare', short: 'C', end: true },
];

const COLLAPSED_KEY = 'prism-sidebar-collapsed';
const EXPANDED_WIDTH = '220px';
const COLLAPSED_WIDTH = '48px';

const linkStyle = ({ isActive }: { isActive: boolean }) => ({
  display: 'block',
  padding: '6px 10px',
  borderRadius: '6px',
  fontSize: '13px',
  color: isActive ? 'var(--prism-sidebar-active-fg)' : 'var(--prism-text-subtle)',
  background: isActive ? 'var(--prism-sidebar-active-bg)' : 'transparent',
  textDecoration: 'none',
});

const collapsedLinkStyle = ({ isActive }: { isActive: boolean }) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '32px',
  height: '32px',
  borderRadius: '6px',
  fontSize: '13px',
  fontWeight: 600,
  color: isActive ? 'var(--prism-sidebar-active-fg)' : 'var(--prism-text-subtle)',
  background: isActive ? 'var(--prism-sidebar-active-bg)' : 'transparent',
  textDecoration: 'none',
  margin: '0 auto',
});

function readInitialCollapsed(): boolean {
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem(COLLAPSED_KEY) === 'true';
}

export function Sidebar() {
  const projects = useProjects();
  const { slug: activeSlug } = useParams<{ slug?: string }>();
  const [collapsed, setCollapsed] = useState<boolean>(readInitialCollapsed);

  useEffect(() => {
    window.localStorage.setItem(COLLAPSED_KEY, String(collapsed));
  }, [collapsed]);

  const toggle = () => setCollapsed((prev) => !prev);

  return (
    <Box
      as="nav"
      w={collapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH}
      bg="var(--prism-bg-surface)"
      borderRightWidth={1}
      borderRightColor="var(--prism-border)"
      px={collapsed ? 1 : 4}
      py={5}
      overflowY="auto"
      flexShrink={0}
      transition="width 0.15s ease, padding 0.15s ease"
    >
      <Box
        display="flex"
        alignItems="center"
        justifyContent={collapsed ? 'center' : 'space-between'}
        mb={6}
        px={collapsed ? 0 : 1}
      >
        {!collapsed && (
          <Link to="/projects" aria-label="Prism home">
            <Logo size="sm" />
          </Link>
        )}
        <IconButton
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          onClick={toggle}
          variant="ghost"
          size="xs"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <Box as="span" fontSize="14px" lineHeight="1">
            {collapsed ? '›' : '‹'}
          </Box>
        </IconButton>
      </Box>

      {collapsed ? (
        <Stack gap={1} align="center">
          {PRIMARY_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              style={collapsedLinkStyle}
              title={item.label}
            >
              {item.short}
            </NavLink>
          ))}
        </Stack>
      ) : (
        <>
          <Stack gap={1}>
            {PRIMARY_NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} style={linkStyle}>
                {item.label}
              </NavLink>
            ))}
          </Stack>

          {projects.data && projects.data.length > 0 && (
            <Box mt={6}>
              <Text
                fontSize="10px"
                textTransform="uppercase"
                letterSpacing="1px"
                color="var(--prism-text-faint)"
                mb={2}
                px={2}
              >
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

          <Text mt={8} fontSize="xs" color="var(--prism-text-faint)" textTransform="uppercase">
            v0.4
          </Text>
        </>
      )}
    </Box>
  );
}
