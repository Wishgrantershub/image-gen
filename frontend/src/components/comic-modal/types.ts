export type StyleKey = "manga" | "pixar" | "superhero";

export type TierDisplay = "Single" | "Story" | "Saga";
export type TierId = "basic" | "premium" | "deluxe";

export const TIER_NAME_TO_ID: Record<TierDisplay, TierId> = {
  Single: "basic",
  Story: "premium",
  Saga: "deluxe",
};

export const TIER_ID_TO_NAME: Record<TierId, TierDisplay> = {
  basic: "Single",
  premium: "Story",
  deluxe: "Saga",
};

export type ComicResult = {
  shareToken: string;
  pdfUrl: string;
  coverUrl: string | null;
};

export type ComicState = {
  photo: string | null;
  photoName: string | null;
  photoFile: File | null;
  heroName: string;
  style: StyleKey | null;
  premise: string;
  tier: TierDisplay | null;
  result: ComicResult | null;
  error: string | null;
};

export const initialState: ComicState = {
  photo: null,
  photoName: null,
  photoFile: null,
  heroName: "",
  style: null,
  premise: "",
  tier: null,
  result: null,
  error: null,
};
