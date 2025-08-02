import type { FC } from 'react';
import type { PanelPickerContextProps, PanelPresetsContextProps } from './context';
import type { ColorPickerProps } from './interface';
export interface ColorPickerPanelProps extends PanelPickerContextProps, Omit<PanelPresetsContextProps, 'onChange'> {
    onClear?: () => void;
    panelRender?: ColorPickerProps['panelRender'];
}
declare const ColorPickerPanel: FC<ColorPickerPanelProps>;
export default ColorPickerPanel;
