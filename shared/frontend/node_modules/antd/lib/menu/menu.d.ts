import * as React from 'react';
import type { MenuProps as RcMenuProps, MenuRef as RcMenuRef } from 'rc-menu';
import type { SiderContextProps } from '../layout/Sider';
import type { ItemType } from './interface';
import type { MenuTheme } from './MenuContext';
export interface MenuProps extends Omit<RcMenuProps, 'items' | '_internalComponents'> {
    theme?: MenuTheme;
    inlineIndent?: number;
    /**
     * @private Internal Usage. Not promise crash if used in production. Connect with chenshuai2144
     *   for removing.
     */
    _internalDisableMenuItemTitleTooltip?: boolean;
    items?: ItemType[];
}
declare const InternalMenu: React.ForwardRefExoticComponent<MenuProps & SiderContextProps & {
    collapsedWidth?: string | number;
} & React.RefAttributes<RcMenuRef>>;
export default InternalMenu;
