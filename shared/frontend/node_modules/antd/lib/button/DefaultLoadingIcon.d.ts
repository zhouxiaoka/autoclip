import React from 'react';
export type DefaultLoadingIconProps = {
    prefixCls: string;
    existIcon: boolean;
    loading?: boolean | object;
    className?: string;
    style?: React.CSSProperties;
    mount: boolean;
};
declare const DefaultLoadingIcon: React.FC<DefaultLoadingIconProps>;
export default DefaultLoadingIcon;
