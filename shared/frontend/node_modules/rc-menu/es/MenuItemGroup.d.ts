import * as React from 'react';
import type { MenuItemGroupType } from './interface';
export interface MenuItemGroupProps extends Omit<MenuItemGroupType, 'type' | 'children' | 'label'> {
    title?: React.ReactNode;
    children?: React.ReactNode;
    /** @private Internal filled key. Do not set it directly */
    eventKey?: string;
    /** @private Do not use. Private warning empty usage */
    warnKey?: boolean;
}
declare const MenuItemGroup: React.ForwardRefExoticComponent<Omit<MenuItemGroupProps, "ref"> & React.RefAttributes<HTMLLIElement>>;
export default MenuItemGroup;
