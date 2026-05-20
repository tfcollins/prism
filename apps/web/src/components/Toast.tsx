import { Box, Text } from '@chakra-ui/react';
import { useEffect } from 'react';

/**
 * Minimal fixed-position toast. Self-contained (no Chakra toaster wiring): the
 * caller controls visibility and auto-dismiss fires after `durationMs`.
 */
export function Toast({
  message,
  onClose,
  durationMs = 5000,
}: {
  message: string;
  onClose: () => void;
  durationMs?: number;
}) {
  useEffect(() => {
    const id = setTimeout(onClose, durationMs);
    return () => clearTimeout(id);
  }, [onClose, durationMs]);

  return (
    <Box
      position="fixed"
      bottom={4}
      right={4}
      zIndex={1000}
      bg="var(--prism-bg-surface)"
      borderWidth={1}
      borderColor="var(--prism-border)"
      borderRadius="md"
      boxShadow="lg"
      px={4}
      py={3}
      maxW="320px"
      role="status"
    >
      <Text fontSize="sm" color="var(--prism-text)">
        {message}
      </Text>
      <Box
        as="button"
        onClick={onClose}
        position="absolute"
        top={1}
        right={2}
        fontSize="xs"
        color="var(--prism-text-faint)"
        cursor="pointer"
      >
        ✕
      </Box>
    </Box>
  );
}
