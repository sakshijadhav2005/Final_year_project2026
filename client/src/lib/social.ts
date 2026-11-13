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
