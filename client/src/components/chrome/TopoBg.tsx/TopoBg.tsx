// src/components/chrome/TopoBg.tsx
import { Box, useColorModeValue } from "@chakra-ui/react";

export default function TopoBg({
  size = 240,        // tile size (px) — smaller => denser lines
  opacity = 0.22,    // line subtlety
}: { size?: number; opacity?: number }) {
  const stroke = useColorModeValue("#6b7280", "#9ca3af"); // light/dark

  const svg = encodeURIComponent(`
    <svg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}' viewBox='0 0 240 240'>
      <defs><style>.l{fill:none;stroke:${stroke};stroke-opacity:${opacity};stroke-width:1}</style></defs>
      <path class="l" d="M-10 20 Q 50 0 110 20 T 230 20" />
      <path class="l" d="M-10 50 Q 40 30 110 50 T 230 50" />
      <path class="l" d="M-10 80 Q 60 60 120 80 T 250 80" />
      <path class="l" d="M-10 110 Q 50 95 120 110 T 250 110" />
      <path class="l" d="M-10 140 Q 70 120 140 140 T 280 140" />
      <path class="l" d="M-10 170 Q 40 150 120 170 T 250 170" />
      <path class="l" d="M-10 200 Q 80 185 150 200 T 310 200" />
      <path class="l" d="M-10 230 Q 50 215 120 230 T 250 230" />
      <path class="l" d="M20 -10 C 40 40, 40 80, 20 140 S 0 220, 20 260" />
      <path class="l" d="M120 -10 C 140 30, 140 90, 120 140 S 100 210, 120 260" />
      <path class="l" d="M200 -10 C 220 50, 220 100, 200 160 S 180 230, 200 260" />
    </svg>
  `);

  return (
    <Box
      aria-hidden
      position="fixed"
      inset={0}
      zIndex={-1}
      pointerEvents="none"             // never block the map
      bgImage={`url("data:image/svg+xml;utf8,${svg}")`}
      bgRepeat="repeat"
      bgSize={`${size}px ${size}px`}
      filter="contrast(0.92)"
    />
  );
}
