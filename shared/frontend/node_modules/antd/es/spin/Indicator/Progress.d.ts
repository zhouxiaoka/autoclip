import * as React from 'react';
export interface ProgressProps {
    prefixCls: string;
    percent: number;
}
declare const Progress: React.FC<Readonly<ProgressProps>>;
export default Progress;
