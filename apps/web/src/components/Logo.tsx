import { Box, Flex, Text } from '@chakra-ui/react';

const SIZES = {
  sm: { mark: 28, wordmark: 18, gap: 10 },
  md: { mark: 40, wordmark: 24, gap: 12 },
  lg: { mark: 64, wordmark: 36, gap: 16 },
};

interface LogoProps {
  /** Visual size — controls both the SVG and the wordmark font size */
  size?: keyof typeof SIZES;
  /** When false, only the mark is rendered (icon-only) */
  showWordmark?: boolean;
  /** Override the mark's primary color (the prism outline). Defaults to the brand cyan. */
  markColor?: string;
}

/**
 * Prism brand mark + wordmark.
 *
 * The mark is an equilateral prism with a white input ray on the left and four
 * refracted colored rays on the right — a visual rhyme with the FFT
 * decomposition the app exists to render.
 */
export function Logo({
  size = 'sm',
  showWordmark = true,
  markColor = 'var(--prism-brand)',
}: LogoProps) {
  const { mark, wordmark, gap } = SIZES[size];

  return (
    <Flex alignItems="center" gap={`${gap}px`}>
      <Box flexShrink={0} color={markColor} lineHeight={0}>
        <PrismMark size={mark} />
      </Box>
      {showWordmark && (
        <Text
          fontSize={`${wordmark}px`}
          fontWeight={700}
          letterSpacing="-0.01em"
          color="var(--prism-text)"
          lineHeight={1}
        >
          Prism
        </Text>
      )}
    </Flex>
  );
}

function PrismMark({ size }: { size: number }) {
  // viewBox is 64x56 — wider than tall to leave room for input ray on the left
  // and refracted rays on the right of the triangle.
  return (
    <svg
      width={size}
      height={(size * 56) / 64}
      viewBox="0 0 64 56"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Prism logo"
    >
      <defs>
        <linearGradient id="prism-mark-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0.22" />
        </linearGradient>
      </defs>
      {/* white input ray, slightly faded */}
      <line
        x1="2"
        y1="36"
        x2="22"
        y2="32"
        stroke="#e2e8f0"
        strokeOpacity="0.55"
        strokeWidth="2"
        strokeLinecap="round"
      />
      {/* the prism */}
      <path
        d="M32 6 L54 44 L10 44 Z"
        fill="url(#prism-mark-fill)"
        stroke="currentColor"
        strokeWidth="2.25"
        strokeLinejoin="round"
      />
      {/* refracted spectrum, top to bottom: red, yellow, green, blue */}
      <line
        x1="42"
        y1="32"
        x2="62"
        y2="22"
        stroke="#f56565"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <line
        x1="44"
        y1="35"
        x2="62"
        y2="32"
        stroke="#ecc94b"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <line
        x1="46"
        y1="38"
        x2="62"
        y2="42"
        stroke="#48bb78"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <line
        x1="48"
        y1="41"
        x2="62"
        y2="52"
        stroke="#4299e1"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}
