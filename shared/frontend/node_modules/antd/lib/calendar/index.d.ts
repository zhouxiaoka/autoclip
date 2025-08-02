import type { Dayjs } from 'dayjs';
import type { CalendarMode, CalendarProps } from './generateCalendar';
import generateCalendar from './generateCalendar';
declare const Calendar: React.FC<Readonly<CalendarProps<Dayjs>>>;
export type CalendarType = typeof Calendar & {
    generateCalendar: typeof generateCalendar;
};
export type { CalendarMode, CalendarProps };
declare const _default: CalendarType;
export default _default;
