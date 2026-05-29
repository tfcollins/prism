import { Box, IconButton, Stack, Text } from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import { Link, NavLink, useParams } from 'react-router-dom';

import { useProjects } from '../api/queries';
import { useAuth } from '../auth/useAuth';
import { Logo } from './Logo';

const BASE_NAV = [
  { to: '/', label: 'Overview', short: 'O', end: true },
  { to: '/projects', label: 'Projects', short: 'P', end: true },
  { to: '/compare', label: 'Compare', short: 'C', end: true },
  { to: '/tokens', label: 'Tokens', short: 'T', end: true },
];
const ADMIN_NAV = { to: '/admin', label: 'Admin', short: 'A', end: true };

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

/**
 * `persistent` (default) is the desktop rail with its collapse toggle.
 * `drawer` is the mobile variant: always expanded, a close button instead of
 * collapse, and every nav tap calls `onNavigate` so the overlay can close.
 */
export function Sidebar({
  variant = 'persistent',
  onNavigate,
}: {
  variant?: 'persistent' | 'drawer';
  onNavigate?: () => void;
}) {
  const projects = useProjects();
  const { user } = useAuth();
  const navItems = user?.is_admin ? [...BASE_NAV, ADMIN_NAV] : BASE_NAV;
  const { slug: activeSlug } = useParams<{ slug?: string }>();
  const isDrawer = variant === 'drawer';
  const [storedCollapsed, setStoredCollapsed] = useState<boolean>(readInitialCollapsed);
  const collapsed = isDrawer ? false : storedCollapsed;

  useEffect(() => {
    if (!isDrawer) window.localStorage.setItem(COLLAPSED_KEY, String(storedCollapsed));
  }, [storedCollapsed, isDrawer]);

  const toggle = () => setStoredCollapsed((prev) => !prev);

  return (
    <Box
      as="nav"
      w={isDrawer ? EXPANDED_WIDTH : collapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH}
      h={isDrawer ? '100%' : undefined}
      // Persistent rail fills the full page height (drawer fills its overlay).
      minH={isDrawer ? '100%' : '100vh'}
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
          <Link to="/" aria-label="Prism home" onClick={onNavigate}>
            <Logo size="sm" />
          </Link>
        )}
        <IconButton
          aria-label={isDrawer ? 'Close menu' : collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          onClick={isDrawer ? onNavigate : toggle}
          variant="ghost"
          size="xs"
          title={isDrawer ? 'Close menu' : collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <Box as="span" fontSize="14px" lineHeight="1">
            {isDrawer ? '✕' : collapsed ? '›' : '‹'}
          </Box>
        </IconButton>
      </Box>

      {collapsed ? (
        <Stack gap={1} align="center">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              style={collapsedLinkStyle}
              title={item.label}
              onClick={onNavigate}
            >
              {item.short}
            </NavLink>
          ))}
        </Stack>
      ) : (
        <>
          <Stack gap={1}>
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                style={linkStyle}
                onClick={onNavigate}
              >
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
                    onClick={onNavigate}
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
