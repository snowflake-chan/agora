export type VotingWindowKind = "standard" | "active_creator";

export type VotingCountdown =
  | { state: "closed" }
  | { state: "days"; days: number; hours: number }
  | { state: "hours"; hours: number }
  | { state: "minutes"; minutes: number };

export function resolveVotingPeriodHours(
  votingPeriodHours: number | null,
  votingStartedAt: string | null,
  votingEndsAt: string | null,
): number | null {
  if (
    typeof votingPeriodHours === "number" &&
    Number.isFinite(votingPeriodHours) &&
    votingPeriodHours > 0
  ) {
    return votingPeriodHours;
  }

  if (!votingStartedAt || !votingEndsAt) return null;
  const startedAt = Date.parse(votingStartedAt);
  const endsAt = Date.parse(votingEndsAt);
  if (!Number.isFinite(startedAt) || !Number.isFinite(endsAt) || endsAt <= startedAt) {
    return null;
  }

  return Math.round((endsAt - startedAt) / 3_600_000);
}

export function isActiveCreatorWindow(
  kind: VotingWindowKind | null,
  votingPeriodHours: number | null,
  votingStartedAt: string | null,
  votingEndsAt: string | null,
): boolean {
  return (
    kind === "active_creator" &&
    resolveVotingPeriodHours(votingPeriodHours, votingStartedAt, votingEndsAt) === 24
  );
}

export function getVotingCountdown(
  votingEndsAt: string | null,
  now = Date.now(),
): VotingCountdown | null {
  if (!votingEndsAt) return null;
  const endsAt = Date.parse(votingEndsAt);
  if (!Number.isFinite(endsAt)) return null;

  const remainingMs = endsAt - now;
  if (remainingMs <= 0) return { state: "closed" };

  const totalMinutes = Math.max(1, Math.ceil(remainingMs / 60_000));
  if (totalMinutes < 60) return { state: "minutes", minutes: totalMinutes };

  const totalHours = Math.ceil(totalMinutes / 60);
  if (totalHours < 24) return { state: "hours", hours: totalHours };

  return {
    state: "days",
    days: Math.floor(totalHours / 24),
    hours: totalHours % 24,
  };
}

export function formatVotingPeriod(
  hours: number | null,
  locale: string,
): string | null {
  if (hours === null || !Number.isFinite(hours) || hours <= 0) return null;
  const useDays = Number.isInteger(hours / 24);
  return new Intl.NumberFormat(locale, {
    style: "unit",
    unit: useDays ? "day" : "hour",
    unitDisplay: "short",
  }).format(useDays ? hours / 24 : hours);
}
