import { Box, Button, Flex, IconButton, Input, Text } from '@chakra-ui/react';
import axios from 'axios';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { useAuth } from '../auth/useAuth';
import { useColorMode } from '../colorMode';
import { Breadcrumbs } from './Breadcrumbs';

export function TopBar({ onMenuClick }: { onMenuClick?: () => void }) {
  const { user, refresh } = useAuth();
  const { colorMode, toggleColorMode } = useColorMode();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');

  function submitSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = search.trim();
    if (q.length >= 2) navigate(`/search?q=${encodeURIComponent(q)}`);
  }

  async function handleLogout() {
    try {
      await api.post('/auth/logout');
    } catch (e) {
      if (!axios.isAxiosError(e)) throw e;
    }
    await refresh();
    navigate('/login');
  }

  return (
    <Flex
      as="header"
      h="56px"
      borderBottomWidth={1}
      borderBottomColor="var(--prism-border)"
      px={{ base: 3, md: 6 }}
      gap={2}
      alignItems="center"
      justifyContent="space-between"
    >
      <Flex alignItems="center" gap={2} flex="1" minW={0}>
        <IconButton
          aria-label="Open menu"
          size="sm"
          variant="ghost"
          display={{ base: 'inline-flex', md: 'none' }}
          onClick={onMenuClick}
        >
          <Box as="span" fontSize="18px" lineHeight="1">
            ☰
          </Box>
        </IconButton>
        <Box flex="1" minW={0}>
          <Breadcrumbs />
        </Box>
      </Flex>
      <Flex alignItems="center" gap={{ base: 2, md: 3 }}>
        <Box as="form" onSubmit={submitSearch} display={{ base: 'none', sm: 'block' }}>
          <Input
            aria-label="Search"
            placeholder="Search…"
            size="sm"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            w={{ sm: '160px', md: '240px' }}
          />
        </Box>
        <IconButton
          aria-label={colorMode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          size="sm"
          variant="outline"
          onClick={toggleColorMode}
        >
          {colorMode === 'dark' ? <SunIcon /> : <MoonIcon />}
        </IconButton>
        <Text
          fontSize="sm"
          color="var(--prism-text-subtle)"
          display={{ base: 'none', sm: 'block' }}
          truncate
          maxW="180px"
        >
          {user?.email ?? 'guest'}
        </Text>
        <Button size="sm" variant="outline" onClick={handleLogout}>
          Sign out
        </Button>
      </Flex>
    </Flex>
  );
}

function SunIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}
