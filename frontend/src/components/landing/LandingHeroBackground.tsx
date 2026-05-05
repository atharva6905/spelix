export default function LandingHeroBackground() {
  return (
    <>
      {/* Glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-[160px] -right-[180px] z-1 h-[780px] w-[780px]"
        style={{
          background:
            "radial-gradient(closest-side, rgba(213,255,69,0.32), rgba(213,255,69,0) 72%)",
          filter: "blur(20px)",
          animation: "breathe 6s ease-in-out infinite",
        }}
      />

      {/* Bar path */}
      <svg
        aria-hidden="true"
        className="landing-barpath pointer-events-none absolute top-0 right-[6%] z-1 h-full w-[120px]"
        viewBox="0 0 120 800"
        preserveAspectRatio="none"
      >
        <path
          d="M 60 0 C 58 200, 64 380, 60 560 C 56 640, 40 700, 50 740 C 60 770, 78 760, 80 730 C 82 700, 70 680, 60 678"
          stroke="rgba(213,255,69,0.07)"
          strokeWidth="1"
          fill="none"
          style={{
            strokeDasharray: 1200,
            strokeDashoffset: 1200,
            animation: "draw 3.5s ease-out 0.4s forwards",
          }}
        />
      </svg>

      {/* Skeleton */}
      <svg
        aria-hidden="true"
        className="landing-hero-skel pointer-events-none absolute right-[8%] top-1/2 z-1 h-[560px] w-[340px] text-landing-text-dim opacity-[.045]"
        viewBox="0 0 340 560"
        style={{
          transformOrigin: "50% 60%",
          animation: "sway 4s ease-in-out infinite",
        }}
      >
        <g
          stroke="currentColor"
          strokeWidth="1.2"
          fill="none"
          strokeLinecap="round"
        >
          {/* head + torso */}
          <line x1="170" y1="60" x2="170" y2="92" />
          <line x1="170" y1="92" x2="148" y2="118" />
          <line x1="170" y1="92" x2="192" y2="118" />
          <line x1="148" y1="118" x2="192" y2="118" />
          <line x1="148" y1="118" x2="150" y2="220" />
          <line x1="192" y1="118" x2="190" y2="220" />
          {/* arms (squat hold) */}
          <line x1="148" y1="118" x2="118" y2="146" />
          <line x1="118" y1="146" x2="100" y2="186" />
          <line x1="100" y1="186" x2="92" y2="226" />
          <line x1="192" y1="118" x2="222" y2="146" />
          <line x1="222" y1="146" x2="240" y2="186" />
          <line x1="240" y1="186" x2="248" y2="226" />
          {/* pelvis */}
          <line x1="150" y1="220" x2="190" y2="220" />
          {/* left leg (squat) */}
          <line x1="150" y1="220" x2="124" y2="298" />
          <line x1="124" y1="298" x2="138" y2="386" />
          <line x1="138" y1="386" x2="118" y2="468" />
          <line x1="118" y1="468" x2="108" y2="500" />
          {/* right leg */}
          <line x1="190" y1="220" x2="216" y2="298" />
          <line x1="216" y1="298" x2="202" y2="386" />
          <line x1="202" y1="386" x2="222" y2="468" />
          <line x1="222" y1="468" x2="232" y2="500" />
          {/* feet */}
          <line x1="92" y1="500" x2="124" y2="504" />
          <line x1="216" y1="500" x2="248" y2="504" />
          {/* bar across shoulders */}
          <line x1="78" y1="118" x2="262" y2="118" />
        </g>
      </svg>
    </>
  );
}
