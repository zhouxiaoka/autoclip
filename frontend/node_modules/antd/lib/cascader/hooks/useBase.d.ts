import type { DirectionType, RenderEmptyHandler } from '../../config-provider';
declare function useBase(customizePrefixCls?: string, direction?: DirectionType): [
    prefixCls: string,
    cascaderPrefixCls: string,
    direction?: DirectionType,
    renderEmpty?: RenderEmptyHandler
];
export default useBase;
