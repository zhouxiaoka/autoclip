import * as React from 'react';
export interface UnitNumberProps {
    prefixCls: string;
    value: string | number;
    offset?: number;
    current?: boolean;
}
export interface SingleNumberProps {
    prefixCls: string;
    value: string;
    count: number;
}
declare const SingleNumber: React.FC<Readonly<SingleNumberProps>>;
export default SingleNumber;
