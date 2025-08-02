import React from 'react';
import type { DirectionType } from '../../config-provider';
export declare const offset = 4;
declare function dropIndicatorRender(props: {
    dropPosition: -1 | 0 | 1;
    dropLevelOffset: number;
    indent: number;
    prefixCls: string;
    direction: DirectionType;
}): React.JSX.Element;
export default dropIndicatorRender;
