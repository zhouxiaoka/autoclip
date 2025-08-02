import * as React from 'react';
import type { AnyObject } from './type';
export declare function withPureRenderTheme<T extends AnyObject = AnyObject>(Component: React.FC<T>): (props: T) => React.JSX.Element;
export interface BaseProps {
    prefixCls?: string;
    style?: React.CSSProperties;
}
declare const genPurePanel: <ComponentProps extends BaseProps = BaseProps>(Component: React.ComponentType<Readonly<ComponentProps>>, alignPropName?: "align" | "dropdownAlign" | "popupAlign", postProps?: (props: ComponentProps) => ComponentProps, defaultPrefixCls?: string, getDropdownCls?: (prefixCls: string) => string) => (props: AnyObject) => React.JSX.Element;
export default genPurePanel;
