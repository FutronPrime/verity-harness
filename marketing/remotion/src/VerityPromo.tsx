import {AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, staticFile, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {VerityIntro} from './VerityIntro';

const TEAL = '#2dd4bf';
const MAG = '#d6299e';
const BG = '#070a0d';
const WHITE = '#eef6f4';
const DIM = '#5e7270';
const MONO = 'SF Mono, Menlo, monospace';

// ── HUD layer over the REAL gameplay recording ───────────────────────────────────────────────
const HudGameplay: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const glow = 8 + Math.sin(frame / 8) * 8;
  // animated coding-axis counter 60 → 93 + bar
  const coding = Math.round(interpolate(frame, [40, 110], [60, 93], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const barW = interpolate(frame, [40, 110], [0.6, 0.93], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  // ✓ TEST PASSED chip pop (and fade out)
  const chip = spring({frame: frame - 120, fps, config: {damping: 10, stiffness: 130}});
  const chipOut = interpolate(frame, [165, 185], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  // lower-third spring up
  const lt = spring({frame: frame - 14, fps, config: {damping: 16, stiffness: 80}});
  const ltY = interpolate(lt, [0, 1], [140, 0]);

  return (
    <AbsoluteFill style={{backgroundColor: BG}}>
      <OffthreadVideo src={staticFile('gameplay-clean.mp4')}
        style={{position: 'absolute', width: '100%', height: '100%', objectFit: 'contain'}} />
      {/* scanlines */}
      <AbsoluteFill style={{backgroundImage: 'repeating-linear-gradient(0deg,#0c1a1d 0 1px,transparent 1px 3px)', opacity: 0.22}} />
      {/* vignette */}
      <AbsoluteFill style={{boxShadow: 'inset 0 0 240px rgba(0,0,0,0.85)'}} />

      {/* corner badge */}
      <div style={{position: 'absolute', top: 44, left: 52, display: 'flex', alignItems: 'center', gap: 18}}>
        <Img src={staticFile('mascot-hawk-icon.png')} style={{width: 96, filter: `drop-shadow(0 0 ${glow}px ${TEAL})`}} />
        <div>
          <div style={{fontFamily: 'Arial Black, sans-serif', color: WHITE, fontSize: 40, letterSpacing: 2}}>VERITY</div>
          <div style={{fontFamily: MONO, color: TEAL, fontSize: 16, letterSpacing: 3}}>THE OPEN-SOURCE FABLE ALTERNATIVE</div>
        </div>
      </div>

      {/* coding-axis stat HUD */}
      <div style={{position: 'absolute', top: 52, right: 64, width: 380, padding: '20px 24px',
        background: 'rgba(7,10,13,0.72)', border: '1.5px solid #15323a', borderRadius: 12, fontFamily: MONO}}>
        <div style={{color: TEAL, fontSize: 17, letterSpacing: 2}}>CODING AXIS · HARNESS ON</div>
        <div style={{color: WHITE, fontSize: 60, fontWeight: 800, lineHeight: 1.05}}>{coding}<span style={{fontSize: 30, color: TEAL}}>%</span></div>
        <div style={{height: 12, background: 'rgba(45,212,191,0.12)', borderRadius: 6, overflow: 'hidden', marginTop: 8}}>
          <div style={{height: '100%', width: `${barW * 100}%`, background: TEAL}} />
        </div>
        <div style={{color: DIM, fontSize: 14, marginTop: 8}}>run the test before "done" · was 60%</div>
      </div>

      {/* ✓ TEST PASSED chip */}
      <div style={{position: 'absolute', top: '40%', left: '50%',
        transform: `translate(-50%,-50%) scale(${chip})`, opacity: chip > 0.02 ? chipOut : 0,
        background: TEAL, color: BG, fontFamily: 'Arial Black, sans-serif', fontSize: 40,
        padding: '14px 34px', borderRadius: 10, boxShadow: `0 0 40px ${TEAL}`}}>✓ TEST PASSED</div>

      {/* lower third */}
      <div style={{position: 'absolute', bottom: 0, width: '100%', transform: `translateY(${ltY}px)`}}>
        <div style={{height: 6, background: TEAL}} />
        <div style={{background: 'rgba(5,8,11,0.88)', padding: '26px 64px'}}>
          <div style={{fontFamily: 'Arial Black, sans-serif', color: WHITE, fontSize: 38}}>
            This Tetris was written by an LLM — <span style={{color: TEAL}}>gated by VERITY</span>.
          </div>
          <div style={{fontFamily: MONO, color: DIM, fontSize: 22, marginTop: 8}}>
            same model, only the discipline changed · github.com/FutronPrime/verity-harness
          </div>
        </div>
      </div>
      <Audio src={staticFile('chiptune.wav')} />
    </AbsoluteFill>
  );
};

// ── CTA end card ─────────────────────────────────────────────────────────────────────────────
const CTA: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const hawk = spring({frame, fps, config: {damping: 14, stiffness: 90}});
  const glow = 14 + Math.sin(frame / 8) * 10;
  const txt = interpolate(frame, [16, 36], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{backgroundColor: BG, alignItems: 'center', justifyContent: 'center'}}>
      <AbsoluteFill style={{background: `radial-gradient(circle at 50% 38%, rgba(45,212,191,0.18), transparent 60%)`}} />
      <Img src={staticFile('mascot-hawk-icon.png')}
        style={{width: 360, transform: `translateY(-120px) scale(${0.7 + hawk * 0.3})`, filter: `drop-shadow(0 0 ${glow}px ${TEAL})`}} />
      <div style={{position: 'absolute', top: '54%', textAlign: 'center', opacity: txt}}>
        <div style={{fontFamily: 'Arial Black, sans-serif', color: WHITE, fontSize: 96, letterSpacing: 8}}>VERITY</div>
        <div style={{fontFamily: MONO, color: TEAL, fontSize: 26, letterSpacing: 5, marginTop: 4}}>THE OPEN-SOURCE FABLE ALTERNATIVE</div>
        <div style={{fontFamily: MONO, color: WHITE, fontSize: 30, marginTop: 30, padding: '14px 30px',
          border: `1.5px solid ${TEAL}`, borderRadius: 10, display: 'inline-block'}}>github.com/FutronPrime/verity-harness</div>
      </div>
      <div style={{position: 'absolute', bottom: 38, width: '92%', height: 3, background: MAG}} />
    </AbsoluteFill>
  );
};

// ── full promo: sting → HUD gameplay → CTA ───────────────────────────────────────────────────
export const VerityPromo: React.FC = () => {
  return (
    <AbsoluteFill style={{backgroundColor: BG}}>
      <Sequence durationInFrames={120}><VerityIntro /></Sequence>
      <Sequence from={120} durationInFrames={480}><HudGameplay /></Sequence>
      <Sequence from={600} durationInFrames={80}><CTA /></Sequence>
    </AbsoluteFill>
  );
};
