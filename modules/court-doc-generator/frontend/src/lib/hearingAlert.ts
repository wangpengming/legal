/** F3 开庭日期提醒：纯函数，可独立测试。 */

export interface HearingCase {
  id: number;
  case_number: string;
  court?: string;
  hearing_date?: string;
}

export interface UpcomingHearing extends HearingCase {
  days_left: number;
}

/**
 * 计算未来 N 天（含今天）内开庭的案件。
 * 无 hearing_date / 非法日期 / 已过期 / 超过 N 天：一律排除，不报错。
 */
export function getUpcomingHearings(
  cases: HearingCase[],
  days = 7,
  now: Date = new Date(),
): UpcomingHearing[] {
  if (!cases || cases.length === 0) return [];

  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const horizon = todayStart + days * 24 * 60 * 60 * 1000;

  const upcoming: UpcomingHearing[] = [];
  for (const c of cases) {
    if (!c.hearing_date) continue;
    const ts = new Date(`${c.hearing_date}T00:00:00`).getTime();
    if (Number.isNaN(ts)) continue;
    if (ts < todayStart || ts > horizon) continue; // 已过期或超出窗口
    const days_left = Math.round((ts - todayStart) / (24 * 60 * 60 * 1000));
    upcoming.push({ ...c, days_left });
  }

  return upcoming.sort((a, b) => a.days_left - b.days_left);
}

/** 当天开庭。 */
export function isToday(hearing: UpcomingHearing): boolean {
  return hearing.days_left === 0;
}