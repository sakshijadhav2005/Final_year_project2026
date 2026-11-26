import type { SocialPlatform } from "@/lib/api";

/** Which platforms each kind of draft can be published to (mirrors the server). */
export const PLATFORMS_FOR_KIND: Record<string, SocialPlatform[]> = {
  linkedin: ["linkedin", "facebook"],
  instagram: ["instagram", "facebook"],
  x: ["x"],
};

/** X's character count, same as the server: links are 23, CJK and emoji count double. */
export function xLength(text: string): number {
  const light = (cp: number) =>
    cp <= 0x10ff || (cp >= 0x2000 && cp <= 0x200d) || (cp >= 0x2010 && cp <= 0x201f) || (cp >= 0x2032 && cp <= 0x2037);
  let total = 0;
  for (const part of text.normalize("NFC").split(/(https?:\/\/\S+)/)) {
    if (/^https?:\/\//.test(part)) total += 23;
    else for (const ch of part) total += light(ch.codePointAt(0) ?? 0) ? 1 : 2;
  }
  return total;
}

/** The format a content type belongs to, for filters ("ig_caption" -> "instagram"). */
export function contentFormat(type: string): string {
  const t = (type || "").toLowerCase().replace(/[-_]/g, "");
  if (["x", "xpost", "tweet", "twitter", "twitterpost"].includes(t)) return "x";
  if (t.includes("linkedin")) return "linkedin";
  if (t.includes("insta") || t.startsWith("ig")) return "instagram";
  if (t.includes("newsletter")) return "newsletter";
  if (t.includes("blog")) return "blog";
  if (t.includes("summary")) return "summary";
  if (t.includes("flyer") || t.includes("poster")) return "flyer";
  return t;
}
