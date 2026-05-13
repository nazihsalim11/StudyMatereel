import React from "react";
import { AbsoluteFill, interpolate, spring, useVideoConfig } from "remotion";
import { WordEntry } from "./types";

interface CaptionsProps {
  words: WordEntry[];
  frame: number;
  fps: number;
}

export const Captions: React.FC<CaptionsProps> = ({ words, frame, fps }) => {
  const currentTime = frame / fps;
  const { width } = useVideoConfig();

  const currentWord = words.find((w) => currentTime >= w.start && currentTime < w.end);

  // Pop-in animation whenever the word changes
  const wordIndex = words.findIndex((w) => currentTime >= w.start && currentTime < w.end);
  const framesSinceWordStart =
    wordIndex >= 0 ? Math.max(0, frame - Math.round(words[wordIndex].start * fps)) : 0;

  const scale = spring({
    frame: framesSinceWordStart,
    fps,
    config: { damping: 14, stiffness: 200, mass: 0.6 },
    from: 0.75,
    to: 1,
  });

  const opacity = interpolate(framesSinceWordStart, [0, 3], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 100,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          width: width * 0.85,
          minHeight: 90,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "18px 36px",
          borderRadius: 18,
          background: "rgba(0, 0, 0, 0.72)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
        }}
      >
        {currentWord && (
          <span
            style={{
              display: "inline-block",
              color: "#ffffff",
              fontSize: 58,
              fontWeight: 900,
              fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
              textAlign: "center",
              letterSpacing: "-1px",
              lineHeight: 1.1,
              textShadow: "0 3px 12px rgba(0,0,0,0.7)",
              transform: `scale(${scale})`,
              opacity,
            }}
          >
            {currentWord.word}
          </span>
        )}
      </div>
    </AbsoluteFill>
  );
};
