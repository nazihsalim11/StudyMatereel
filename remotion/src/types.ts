export interface WordEntry {
  word: string;
  start: number; // seconds from slide start
  end: number;
}

export interface SlideSubtitles {
  slide: number;
  duration: number;
  words: WordEntry[];
}

export interface SlideData {
  imageUrl: string;
  audioUrl: string;
  duration: number; // seconds
}
