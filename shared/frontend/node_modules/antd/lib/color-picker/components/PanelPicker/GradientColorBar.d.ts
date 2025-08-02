import * as React from 'react';
import type { GradientColor } from '../../color';
import type { PanelPickerContextProps } from '../../context';
export interface GradientColorBarProps extends PanelPickerContextProps {
    colors: GradientColor;
}
declare const _default: React.MemoExoticComponent<(props: GradientColorBarProps) => React.JSX.Element | null>;
export default _default;
