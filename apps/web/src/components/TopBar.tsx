import { Box, Button, Flex, Text } from '@chakra-ui/react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { useAuth } from '../auth/useAuth';
import { Breadcrumbs } from './Breadcrumbs';

export function TopBar() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();

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
      borderBottomColor="#2d3748"
      px={6}
      alignItems="center"
      justifyContent="space-between"
    >
      <Box flex="1" minW={0}>
        <Breadcrumbs />
      </Box>
      <Flex alignItems="center" gap={3}>
        <Text fontSize="sm" color="#a0aec0">
          {user?.email ?? 'guest'}
        </Text>
        <Button size="sm" variant="outline" onClick={handleLogout}>
          Sign out
        </Button>
      </Flex>
    </Flex>
  );
}
