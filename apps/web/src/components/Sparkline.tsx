/**
 * Tiny dependency-free SVG sparkline — an area+line micro-chart for stat cards.
 * Renders on a transparent background so it inherits the card's surface; the
 * fill is a soft gradient of the trace color for the "scope readout" feel.
 */
export function Sparkline({
  values,
  color,
  width = 120,
  height = 34,
  strokeWidth = 1.5,
}: {
  values: number[];
  color: string;
  width?: number;
  height?: number;
  strokeWidth?: number;
}) {
  if (values.length < 2) return null;

  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const pad = strokeWidth;
  const innerH = height - pad * 2;
  const stepX = width / (values.length - 1);

  const pts = values.map((v, i) => {
    const x = i * stepX;
    const y = pad + innerH - ((v - min) / span) * innerH;
    return [x, y] as const;
  });

  const line = pts
    .map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(' ');
  const area = `${line} L${width},${height} L0,${height} Z`;
  // Stable-but-unique gradient id without Math.random (varies by color + length).
  const gid = `spark-${color.replace(/[^a-z0-9]/gi, '')}-${values.length}`;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      style={{ display: 'block' }}
    >
      <defs>
        <linearGradient id={gid} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`} />
      <path d={line} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinejoin="round" />
    </svg>
  );
}
