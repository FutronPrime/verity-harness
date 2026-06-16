import {Composition} from 'remotion';
import {VerityIntro} from './VerityIntro';

// Drop the repo's assets into ./public so staticFile() can resolve them:
//   mkdir -p public && cp ../../assets/{logo.png,mascot-hawk-icon.png,scorecard.png,demo-tetris-comparison.png} public/
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
    </>
  );
};
