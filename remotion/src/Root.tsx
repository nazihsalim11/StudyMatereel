import React from "react";
import { Composition } from "remotion";
import { StudyReel, StudyReelSchema } from "./StudyReel";

const DEFAULT_PROPS = {
  slides: [
    {
      imageUrl: "",
      audioUrl: "",
      duration: 5,
    },
  ],
  subtitles: [],
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="StudyReel"
      component={StudyReel}
      // calculateMetadata derives total duration from the props at render-time
      calculateMetadata={({ props }) => ({
        durationInFrames: Math.max(
          30,
          props.slides.reduce(
            (sum: number, s: { duration: number }) => sum + Math.round(s.duration * 30),
            0
          )
        ),
        fps: 30,
        width: 1080,
        height: 1920,
      })}
      fps={30}
      width={1080}
      height={1920}
      schema={StudyReelSchema}
      defaultProps={DEFAULT_PROPS}
    />
  );
};
