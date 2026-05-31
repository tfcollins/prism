import { Box, Flex } from '@chakra-ui/react';
import { type ReactNode, useState } from 'react';

import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function AppShell({ children }: { children: ReactNode }) {
  const [navOpen, setNavOpen] = useState(false);
  const closeNav = () => setNavOpen(false);

  return (
    <Flex minH="100vh" direction="column">
      {/* Spectral hairline — the "Prism" refraction signature, spanning the
          full width above everything. The one bold brand moment. */}
      <Box h="3px" flexShrink={0} backgroundImage="var(--prism-spectrum-gradient)" />
      <Flex flex="1" minH={0}>
        {/* Persistent rail on md+; hidden on mobile (the drawer replaces it). */}
        <Box display={{ base: 'none', md: 'block' }} flexShrink={0}>
          <Sidebar />
        </Box>

        {/* Mobile overlay drawer */}
        {navOpen && (
          <Box display={{ base: 'block', md: 'none' }}>
            <Box position="fixed" inset={0} bg="blackAlpha.600" zIndex={1300} onClick={closeNav} />
            <Box position="fixed" top={0} left={0} bottom={0} zIndex={1400}>
              <Sidebar variant="drawer" onNavigate={closeNav} />
            </Box>
          </Box>
        )}

        <Box flex="1" minW={0} display="flex" flexDirection="column">
          <TopBar onMenuClick={() => setNavOpen(true)} />
          <Box as="main" flex="1" p={{ base: 4, md: 6 }} overflowY="auto">
            {children}
          </Box>
        </Box>
      </Flex>
    </Flex>
  );
}
