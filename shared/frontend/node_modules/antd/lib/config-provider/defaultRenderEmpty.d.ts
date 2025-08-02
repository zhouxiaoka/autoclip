import React from 'react';
type ComponentName = 'Table' | 'Table.filter' | 'List' | 'Select' | 'TreeSelect' | 'Cascader' | 'Transfer' | 'Mentions';
interface EmptyProps {
    componentName?: ComponentName;
}
declare const DefaultRenderEmpty: React.FC<EmptyProps>;
export type RenderEmptyHandler = (componentName?: ComponentName) => React.ReactNode;
export default DefaultRenderEmpty;
