import * as React from 'react';
import type { StatisticProps } from './Statistic';
import type { FormatConfig, valueType } from './utils';
export type TimerType = 'countdown' | 'countup';
export interface StatisticTimerProps extends FormatConfig, StatisticProps {
    type: TimerType;
    format?: string;
    /**
     * Only to be called when the type is `countdown`.
     */
    onFinish?: () => void;
    onChange?: (value?: valueType) => void;
}
declare const StatisticTimer: React.FC<StatisticTimerProps>;
export default StatisticTimer;
