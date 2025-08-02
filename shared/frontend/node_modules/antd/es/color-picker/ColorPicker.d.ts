import React from 'react';
import type { ColorPickerProps } from './interface';
type CompoundedComponent = React.FC<ColorPickerProps> & {
    _InternalPanelDoNotUseOrYouWillBeFired: typeof PurePanel;
};
declare const ColorPicker: CompoundedComponent;
declare const PurePanel: (props: import("../_util/type").AnyObject) => React.JSX.Element;
export default ColorPicker;
