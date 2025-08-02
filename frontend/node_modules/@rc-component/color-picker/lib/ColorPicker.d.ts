import type { CSSProperties } from 'react';
import React from 'react';
import { type Components } from './hooks/useComponent';
import type { BaseColorPickerProps, ColorGenInput } from './interface';
export interface ColorPickerProps extends Omit<BaseColorPickerProps, 'color'> {
    value?: ColorGenInput;
    defaultValue?: ColorGenInput;
    className?: string;
    style?: CSSProperties;
    /** Get panel element  */
    panelRender?: (panel: React.ReactElement) => React.ReactElement;
    /** Disabled alpha selection */
    disabledAlpha?: boolean;
    components?: Components;
}
declare const ColorPicker: React.ForwardRefExoticComponent<ColorPickerProps & React.RefAttributes<HTMLDivElement>>;
export default ColorPicker;
