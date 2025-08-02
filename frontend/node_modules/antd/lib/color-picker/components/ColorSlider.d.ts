import * as React from 'react';
import type { BaseSliderProps } from '@rc-component/color-picker';
import { UnstableContext } from 'rc-slider';
import type { GetContextProp } from '../../_util/type';
export interface GradientColorSliderProps extends Omit<BaseSliderProps, 'value' | 'onChange' | 'onChangeComplete' | 'type'> {
    value: number[];
    onChange?: (value: number[]) => void;
    onChangeComplete: (value: number[]) => void;
    range?: boolean;
    className?: string;
    activeIndex?: number;
    onActive?: (index: number) => void;
    type: BaseSliderProps['type'] | 'gradient';
    onDragStart?: GetContextProp<typeof UnstableContext, 'onDragStart'>;
    onDragChange?: GetContextProp<typeof UnstableContext, 'onDragChange'>;
    onKeyDelete?: (index: number) => void;
}
export declare const GradientColorSlider: (props: GradientColorSliderProps) => React.JSX.Element;
declare const SingleColorSlider: (props: BaseSliderProps) => React.JSX.Element;
export default SingleColorSlider;
