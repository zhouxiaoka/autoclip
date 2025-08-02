import * as React from 'react';
import type { ListProps, ListRef } from './List';
declare const List: <Item = any>(props: React.PropsWithChildren<ListProps<Item>> & {
    ref?: React.Ref<ListRef>;
}) => React.ReactElement;
export default List;
