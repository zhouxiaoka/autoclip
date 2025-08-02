import type { CountdownProps } from './Countdown';
import Countdown from './Countdown';
import type { StatisticProps } from './Statistic';
import Statistic from './Statistic';
import type { StatisticTimerProps } from './Timer';
import Timer from './Timer';
export type { CountdownProps, StatisticTimerProps, StatisticProps };
type CompoundedComponent = {
    /**
     * @deprecated Please use `Statistic.Timer` instead
     */
    Countdown: typeof Countdown;
    Timer: typeof Timer;
};
export type CompoundedStatistic = typeof Statistic & CompoundedComponent;
declare const _default: CompoundedStatistic;
export default _default;
