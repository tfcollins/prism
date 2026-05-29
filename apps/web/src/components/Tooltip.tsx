import { Portal, Tooltip as ChakraTooltip } from '@chakra-ui/react';
import type { ReactElement, ReactNode } from 'react';

/**
 * Small wrapper over Chakra v3's Tooltip anatomy so call sites can just write
 * `<Tooltip content="…"><button/></Tooltip>`. The child must be a single
 * element (it becomes the trigger via `asChild`).
 */
export function Tooltip({
  content,
  children,
  showArrow = true,
}: {
  content: ReactNode;
  children: ReactElement;
  showArrow?: boolean;
}) {
  return (
    <ChakraTooltip.Root openDelay={200} closeDelay={100}>
      <ChakraTooltip.Trigger asChild>{children}</ChakraTooltip.Trigger>
      <Portal>
        <ChakraTooltip.Positioner>
          <ChakraTooltip.Content
            maxW="260px"
            fontSize="xs"
            bg="var(--prism-bg-surface)"
            color="var(--prism-text)"
            borderWidth={1}
            borderColor="var(--prism-border)"
          >
            {showArrow && (
              <ChakraTooltip.Arrow>
                <ChakraTooltip.ArrowTip />
              </ChakraTooltip.Arrow>
            )}
            {content}
          </ChakraTooltip.Content>
        </ChakraTooltip.Positioner>
      </Portal>
    </ChakraTooltip.Root>
  );
}
