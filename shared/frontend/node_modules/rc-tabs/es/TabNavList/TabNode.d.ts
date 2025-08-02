import * as React from 'react';
import type { EditableConfig, Tab } from '../interface';
export interface TabNodeProps {
    id: string;
    prefixCls: string;
    tab: Tab;
    active: boolean;
    focus: boolean;
    closable?: boolean;
    editable?: EditableConfig;
    onClick?: (e: React.MouseEvent | React.KeyboardEvent) => void;
    onResize?: (width: number, height: number, left: number, top: number) => void;
    renderWrapper?: (node: React.ReactElement) => React.ReactElement;
    removeAriaLabel?: string;
    tabCount: number;
    currentPosition: number;
    removeIcon?: React.ReactNode;
    onKeyDown: React.KeyboardEventHandler;
    onMouseDown: React.MouseEventHandler;
    onMouseUp: React.MouseEventHandler;
    onFocus: React.FocusEventHandler;
    onBlur: React.FocusEventHandler;
    style?: React.CSSProperties;
}
declare const TabNode: React.FC<TabNodeProps>;
export default TabNode;
