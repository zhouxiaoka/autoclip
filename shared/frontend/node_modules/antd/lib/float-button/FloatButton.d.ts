import React from 'react';
import type BackTop from './BackTop';
import type FloatButtonGroup from './FloatButtonGroup';
import type { FloatButtonElement, FloatButtonProps } from './interface';
import type PurePanel from './PurePanel';
export declare const floatButtonPrefixCls = "float-btn";
declare const InternalFloatButton: React.ForwardRefExoticComponent<FloatButtonProps & React.RefAttributes<FloatButtonElement>>;
type CompoundedComponent = typeof InternalFloatButton & {
    Group: typeof FloatButtonGroup;
    BackTop: typeof BackTop;
    _InternalPanelDoNotUseOrYouWillBeFired: typeof PurePanel;
};
declare const FloatButton: CompoundedComponent;
export default FloatButton;
