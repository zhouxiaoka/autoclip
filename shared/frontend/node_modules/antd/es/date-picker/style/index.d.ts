import { genPanelStyle } from './panel';
import type { ComponentToken, PanelComponentToken, PickerPanelToken } from './token';
import { initPanelComponentToken, initPickerPanelToken } from './token';
export type { ComponentToken, PanelComponentToken, PickerPanelToken };
export { initPickerPanelToken, initPanelComponentToken, genPanelStyle };
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
