import * as React from 'react';
import type { SubMenuType } from './interface';
export interface SubMenuProps extends Omit<SubMenuType, 'ref' | 'key' | 'children' | 'label'> {
    title?: React.ReactNode;
    children?: React.ReactNode;
    /**
     * @deprecated No longer needed, it can now be safely deleted.
     * @see: https://github.com/ant-design/ant-design/pull/30638
     */
    level?: number;
}
declare const SubMenu: React.FC<SubMenuProps>;
export default SubMenu;
