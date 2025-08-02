import * as React from 'react';
import type { AnyObject } from '../_util/type';
import type { TableLocale } from './interface';
interface DefaultExpandIconProps<RecordType = AnyObject> {
    prefixCls: string;
    record: RecordType;
    expanded: boolean;
    expandable: boolean;
    onExpand: (record: RecordType, e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => void;
}
declare function renderExpandIcon(locale: TableLocale): <RecordType extends AnyObject = AnyObject>(props: DefaultExpandIconProps<RecordType>) => React.JSX.Element;
export default renderExpandIcon;
