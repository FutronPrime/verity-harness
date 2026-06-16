import {AbsoluteFill, Img, staticFile, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

// VERITY intro sting — logo + Truth Hawk mascot, animated. The hawk floats + its V pulses; the logo
// slides up; a magenta underline wipes; the tagline fades. Brand palette only. Silent (mascot never talks).
const TEAL = '#2dd4bf';
const MAG = '#d6299e';
const BG = '#070a0d';

export const VerityIntro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // hawk: spring-in scale + gentle float + glow pulse
  const hawkIn = spring({frame, fps, config: {damping: 14, stiffness: 90}});
  const float = Math.sin(frame / 14) * 10;
  const glow = 8 + Math.sin(frame / 8) * 8;

  // logo: slide up + fade after the hawk lands
  const logoY = interpolate(frame, [18, 42], [60, 0], {extrapolateRight: 'clamp'});
  const logoOp = interpolate(frame, [18, 42], [0, 1], {extrapolateRight: 'clamp'});

  // magenta underline wipe
  const underline = interpolate(frame, [44, 66], [0, 420], {extrapolateRight: 'clamp'});

  // tagline fade
  const tagOp = interpolate(frame, [70, 92], [0, 1], {extrapolateRight: 'clamp'});

  return (
    <AbsoluteFill style={{backgroundColor: BG, alignItems: 'center', justifyContent: 'center', fontFamily: 'Arial Black, Arial, sans-serif'}}>
      {/* faint scanline grid */}
      <AbsoluteFill style={{backgroundImage: `repeating-linear-gradient(0deg, #0c1a1d 0 1px, transparent 1px 3px)`, opacity: 0.4}} />

      {/* Truth Hawk mascot */}
      <Img
        src={staticFile('mascot-hawk-icon.png')}
        style={{
          width: 540,
          transform: `translateY(${-90 + float}px) scale(${0.6 + hawkIn * 0.4})`,
          filter: `drop-shadow(0 0 ${glow}px ${TEAL})`,
        }}
      />

      {/* Logo */}
      <Img
        src={staticFile('logo.png')}
        style={{width: 760, transform: `translateY(${120 + logoY}px)`, opacity: logoOp}}
      />

      {/* magenta underline */}
      <div style={{position: 'absolute', top: '74%', width: underline, height: 4, background: MAG}} />

      {/* tagline */}
      <div style={{position: 'absolute', top: '80%', color: '#8fb8b1', fontFamily: 'SF Mono, Menlo, monospace', fontSize: 26, letterSpacing: 3, opacity: tagOp}}>
        the truth — not a fable.
      </div>
    </AbsoluteFill>
  );
};
