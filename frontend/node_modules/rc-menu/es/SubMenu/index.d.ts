import * as React from 'react';
import type { SubMenuType } from '../interface';
export interface SubMenuProps extends Omit<SubMenuType, 'key' | 'children' | 'label'> {
    title?: React.ReactNode;
    children?: React.ReactNode;
    /** @private Used for rest popup. Do not use in your prod */
    internalPopupClose?: boolean;
    /** @private Internal filled key. Do not set it directly */
    eventKey?: string;
    /** @private Do not use. Private warning empty usage */
    warnKey?: boolean;
}
declare const SubMenu: React.ForwardRefExoticComponent<Omit<SubMenuProps, "ref"> & React.RefAttributes<HTMLLIElement>>;
export default SubMenu;
