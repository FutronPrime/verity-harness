import {Composition} from 'remotion';
import {VerityIntro} from './VerityIntro';
import {VerityPromo} from './VerityPromo';

// Drop the repo's assets into ./public so staticFile() can resolve them:
//   mkdir -p public && cp ../../assets/{logo.png,scorecard.png,demo-tetris-comparison.png} public/
//   cp ../../assets/mascot-hawk.png public/mascot-hawk-icon.png   (+ gameplay-clean.mp4, chiptune.wav)
export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="VerityIntro"
        component={VerityIntro}
        durationInFrames={150}   // 5s @ 30fps
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="VerityPromo"
        component={VerityPromo}
        durationInFrames={680}   // sting(120) + HUD gameplay(480) + CTA(80) @ 30fps ≈ 22.7s
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
