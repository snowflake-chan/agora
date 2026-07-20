export const GUILD_LEVEL_COLORS = [
  "",
  "#cd7f32",
  "#c0c0c0",
  "#ffd700",
  "#b9f2ff",
  "#ff4500",
] as const;

export function guildLevelColor(level: number) {
  return GUILD_LEVEL_COLORS[level] || "#888";
}

export function guildLevelKey(level: number) {
  const normalized = Number.isInteger(level) && level >= 1 && level <= 5 ? level : 1;
  return `guild.level.${normalized}`;
}

export function isGuildLogoImage(value: string | null | undefined) {
  return Boolean(value && /^(https?:\/\/|\/)/i.test(value.trim()));
}
