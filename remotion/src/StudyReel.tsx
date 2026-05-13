import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  Series,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { z } from "zod";
import { Captions } from "./Captions";
import { SlideSubtitles, WordEntry } from "./types";

// ── Zod schema (used for Remotion Studio type-checking) ────────────────────────

export const StudyReelSchema = z.object({
  slides: z.array(
    z.object({
      imageUrl: z.string(),
      audioUrl: z.string(),
      duration: z.number().positive(),
    })
  ),
  subtitles: z.array(
    z.object({
      slide: z.number(),
      duration: z.number(),
      words: z.array(
        z.object({ word: z.string(), start: z.number(), end: z.number() })
      ),
    })
  ),
});

type StudyReelProps = z.infer<typeof StudyReelSchema>;

// ── Root composition ──────────────────────────────────────────────────────────

export const StudyReel: React.FC<StudyReelProps> = ({ slides, subtitles }) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Series>
        {slides.map((slide, i) => {
          const durationInFrames = Math.max(1, Math.round(slide.duration * fps));
          const slideSubtitles = subtitles.find((s) => s.slide === i);

          return (
            <Series.Sequence key={i} durationInFrames={durationInFrames}>
              <SlideScene
                imageUrl={slide.imageUrl}
                audioUrl={slide.audioUrl}
                words={slideSubtitles?.words ?? []}
              />
            </Series.Sequence>
          );
        })}
      </Series>
    </AbsoluteFill>
  );
};

// ── Per-slide scene ───────────────────────────────────────────────────────────

const SlideScene: React.FC<{
  imageUrl: string;
  audioUrl: string;
  words: WordEntry[];
}> = ({ imageUrl, audioUrl, words }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  return (
    <AbsoluteFill>
      {/* Blurred, colour-boosted background */}
      {imageUrl && (
        <AbsoluteFill
          style={{
            filter: "blur(24px) brightness(0.35) saturate(1.8)",
            transform: "scale(1.12)", // hide blur edges
          }}
        >
          <Img
            src={imageUrl}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </AbsoluteFill>
      )}

      {/* Subtle vignette overlay */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.6) 100%)",
        }}
      />

      {/* Centred slide image — leaves room for captions at the bottom */}
      {imageUrl && (
        <AbsoluteFill
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: `${height * 0.04}px ${width * 0.05}px ${height * 0.18}px`,
          }}
        >
          <Img
            src={imageUrl}
            style={{
              maxWidth: "100%",
              maxHeight: "100%",
              objectFit: "contain",
              borderRadius: 20,
              boxShadow: "0 24px 80px rgba(0,0,0,0.85)",
            }}
          />
        </AbsoluteFill>
      )}

      {/* Audio track */}
      {audioUrl && <Audio src={audioUrl} />}

      {/* Word-by-word captions */}
      <Captions words={words} frame={frame} fps={fps} />
    </AbsoluteFill>
  );
};
