export type RecognizedCity = "Pune" | "Mumbai" | "Bengaluru" | "Virtual";

export interface EventLocationInput {
  name?: string | null;
  topic?: string | null;
  organizer_name?: string | null;
}

/**
 * Confidently detects event location/city from existing event text fields.
 * Returns null if no recognized location is detected.
 */
export function getEventCity(event?: EventLocationInput | null): RecognizedCity | null {
  if (!event) return null;

  const parts = [event.name, event.topic, event.organizer_name].filter(Boolean) as string[];
  if (parts.length === 0) return null;

  const text = parts.join(" ");

  if (/\bpune\b/i.test(text)) {
    return "Pune";
  }
  if (/\bmumbai\b|\bbombay\b/i.test(text)) {
    return "Mumbai";
  }
  if (/\b(bengaluru|bangalore)\b/i.test(text)) {
    return "Bengaluru";
  }
  if (/\b(online|virtual|remote|webinar)\b/i.test(text)) {
    return "Virtual";
  }

  return null;
}

/**
 * Returns icon and formatted label for a recognized city.
 */
export function getCityBadge(city: RecognizedCity): { label: string; icon: string } {
  switch (city) {
    case "Pune":
      return { label: "Pune", icon: "📍" };
    case "Mumbai":
      return { label: "Mumbai", icon: "📍" };
    case "Bengaluru":
      return { label: "Bengaluru", icon: "📍" };
    case "Virtual":
      return { label: "Virtual", icon: "💻" };
  }
}
