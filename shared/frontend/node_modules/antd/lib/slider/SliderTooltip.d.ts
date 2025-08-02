import * as React from 'react';
import type { SliderRef } from 'rc-slider/lib/Slider';
import type { TooltipProps } from '../tooltip';
export type SliderTooltipProps = TooltipProps & {
    draggingDelete?: boolean;
    value?: number;
};
declare const SliderTooltip: React.ForwardRefExoticComponent<SliderTooltipProps & React.RefAttributes<SliderRef>>;
export default SliderTooltip;
