import { Box, Flex } from '@chakra-ui/react';
import type { ReactNode } from 'react';

import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <Flex minH="100vh">
      <Sidebar />
      <Box flex="1" display="flex" flexDirection="column">
        <TopBar />
        <Box as="main" flex="1" p={6} overflowY="auto">
          {children}
        </Box>
      </Box>
    </Flex>
  );
}
