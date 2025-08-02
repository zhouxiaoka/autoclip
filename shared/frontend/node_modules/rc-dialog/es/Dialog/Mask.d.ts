import * as React from 'react';
export type MaskProps = {
    prefixCls: string;
    visible: boolean;
    motionName?: string;
    style?: React.CSSProperties;
    maskProps?: React.HTMLAttributes<HTMLDivElement>;
    className?: string;
};
declare const Mask: React.FC<MaskProps>;
export default Mask;
