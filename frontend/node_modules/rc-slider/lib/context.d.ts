import * as React from 'react';
import type { AriaValueFormat, Direction, SliderClassNames, SliderStyles } from './interface';
export interface SliderContextProps {
    min: number;
    max: number;
    includedStart: number;
    includedEnd: number;
    direction: Direction;
    disabled?: boolean;
    keyboard?: boolean;
    included?: boolean;
    step: number | null;
    range?: boolean;
    tabIndex: number | number[];
    ariaLabelForHandle?: string | string[];
    ariaLabelledByForHandle?: string | string[];
    ariaRequired?: boolean;
    ariaValueTextFormatterForHandle?: AriaValueFormat | AriaValueFormat[];
    classNames: SliderClassNames;
    styles: SliderStyles;
}
declare const SliderContext: React.Context<SliderContextProps>;
export default SliderContext;
export interface UnstableContextProps {
    onDragStart?: (info: {
        rawValues: number[];
        draggingIndex: number;
        draggingValue: number;
    }) => void;
    onDragChange?: (info: {
        rawValues: number[];
        deleteIndex: number;
        draggingIndex: number;
        draggingValue: number;
    }) => void;
}
/** @private NOT PROMISE AVAILABLE. DO NOT USE IN PRODUCTION. */
export declare const UnstableContext: React.Context<UnstableContextProps>;
