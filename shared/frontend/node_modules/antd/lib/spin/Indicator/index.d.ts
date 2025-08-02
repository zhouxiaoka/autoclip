import * as React from 'react';
export interface IndicatorProps {
    prefixCls: string;
    indicator?: React.ReactNode;
    percent?: number;
}
export default function Indicator(props: IndicatorProps): React.JSX.Element;
