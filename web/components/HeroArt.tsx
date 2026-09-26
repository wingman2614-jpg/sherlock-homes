// Flat, outlined illustration in the Happy Hues style: a browser window with a
// neighborhood map, a small chart and a coral magnifying-glass badge.
export default function HeroArt({ className = "" }: { className?: string }) {
  const S = "#020826"; // stroke
  return (
    <svg viewBox="0 0 560 440" className={className} role="img" aria-label="Illustration of a housing map being inspected with a magnifying glass">
      {/* back window */}
      <rect x="100" y="30" width="400" height="300" rx="8" fill="#eaddcf" stroke={S} strokeWidth="4" />
      <line x1="100" y1="82" x2="500" y2="82" stroke={S} strokeWidth="4" />
      {[128, 158, 188].map((x) => <circle key={x} cx={x} cy="56" r="8" fill="#fffffe" stroke={S} strokeWidth="4" />)}
      {/* shadow of front window */}
      <rect x="84" y="150" width="340" height="270" rx="8" fill="#b8ab9c" />
      {/* front window */}
      <rect x="60" y="130" width="340" height="270" rx="8" fill="#fffffe" stroke={S} strokeWidth="4" />
      {/* map panel */}
      <rect x="84" y="156" width="190" height="220" rx="4" fill="#fffffe" stroke={S} strokeWidth="4" />
      <path d="M86 158 C 92 240, 150 250, 190 256 C 240 262, 268 300, 272 374 L 86 374 Z" fill="#8c7851" stroke={S} strokeWidth="4" strokeLinejoin="round" />
      <path d="M120 300 l30 -18 l32 10 l-8 34 l-38 6 z" fill="#eaddcf" stroke={S} strokeWidth="3" />
      <path d="M196 318 l26 -8 l14 24 l-24 16 z" fill="#f25042" stroke={S} strokeWidth="3" />
      {/* pin */}
      <circle cx="210" cy="206" r="10" fill="#fffffe" stroke={S} strokeWidth="4" />
      <line x1="210" y1="188" x2="210" y2="196" stroke={S} strokeWidth="4" strokeLinecap="round" />
      <line x1="210" y1="216" x2="210" y2="224" stroke={S} strokeWidth="4" strokeLinecap="round" />
      {/* side column: bars + list */}
      <rect x="292" y="156" width="84" height="54" rx="4" fill="#8c7851" stroke={S} strokeWidth="4" />
      <rect x="292" y="224" width="84" height="54" rx="4" fill="#eaddcf" stroke={S} strokeWidth="4" />
      {[300, 326, 352].map((y, i) => (
        <g key={y}>
          <circle cx="302" cy={y} r="7" fill={i === 0 ? "#8c7851" : "#fffffe"} stroke={S} strokeWidth="4" />
          <line x1="318" y1={y} x2="372" y2={y} stroke={S} strokeWidth="4" strokeLinecap="round" />
        </g>
      ))}
      {/* coral badge with magnifying glass */}
      <g transform="translate(470 120)">
        <path
          d="M0 -62 L12 -48 L30 -55 L34 -36 L52 -32 L46 -14 L61 -2 L46 10 L52 28 L34 32 L30 51 L12 44 L0 58 L-12 44 L-30 51 L-34 32 L-52 28 L-46 10 L-61 -2 L-46 -14 L-52 -32 L-34 -36 L-30 -55 L-12 -48 Z"
          fill="#f25042" stroke={S} strokeWidth="4" strokeLinejoin="round"
        />
        <circle r="38" fill="#8c7851" stroke={S} strokeWidth="4" />
        <circle cx="-6" cy="-6" r="16" fill="#fffffe" stroke={S} strokeWidth="5" />
        <line x1="6" y1="6" x2="22" y2="22" stroke={S} strokeWidth="7" strokeLinecap="round" />
      </g>
    </svg>
  );
}
