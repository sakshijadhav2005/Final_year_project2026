/**
 * Time helpers for values from the API.
 *
 * The server stores times in UTC. On SQLite (local development) the zone is dropped, so a
 * timestamp arrives as "2026-11-26T18:05:06" with no "Z". `new Date()` reads that as local
 * time, which puts it hours off (5½ in India). Always parse server timestamps with
 * `parseServerTime`, and plain calendar dates ("2026-11-26") with `parseCalendarDate`.
 */

const HAS_ZONE = /(?:[zZ]|[+-]\d\d:?\d\d)$/;

/** A server timestamp as a Date, reading a zone-less value as UTC. */
export function parseServerTime(value: string): Date {
  return new Date(HAS_ZONE.test(value) ? value : `${value}Z`);
}

/** A plain calendar date ("YYYY-MM-DD") as local midnight, so it never shifts a day. */
export function parseCalendarDate(value: string): Date {
  const [y, m, d] = value.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** Local calendar day of a time as YYYY-MM-DD, the format a date input uses. */
export function localDayKey(value: string | Date): string {
  const d = typeof value === "string" ? parseServerTime(value) : value;
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}
