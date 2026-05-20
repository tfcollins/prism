import { Box, Flex, Text } from '@chakra-ui/react';

/**
 * Placeholder shown while a plot's data is loading. Holds the plot's footprint
 * so the layout doesn't jump when the figure arrives, and reads less abruptly
 * than a bare spinner.
 */
export function PlotSkeleton({ height = 340, label }: { height?: number; label?: string }) {
  return (
    <Flex
      align="center"
      justify="center"
      h={`${height}px`}
      w="100%"
      borderRadius="md"
      bg="var(--prism-bg-plot)"
      borderWidth={1}
      borderColor="var(--prism-border)"
      position="relative"
      overflow="hidden"
    >
      <Box
        position="absolute"
        inset={0}
        css={{
          background:
            'linear-gradient(90deg, transparent 0%, var(--prism-bg-hover) 50%, transparent 100%)',
          backgroundSize: '200% 100%',
          animation: 'prism-shimmer 1.4s ease-in-out infinite',
          '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
        }}
      />
      {label && (
        <Text fontSize="sm" color="var(--prism-text-faint)" zIndex={1}>
          {label}
        </Text>
      )}
    </Flex>
  );
}
