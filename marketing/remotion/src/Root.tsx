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
        durationInFrames={885}   // sting(75) + HUD gameplay(690) + CTA(120) @ 30fps ≈ 29.5s (fits 25.5s VO)
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
