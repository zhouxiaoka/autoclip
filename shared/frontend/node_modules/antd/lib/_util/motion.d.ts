import type { CSSMotionProps } from 'rc-motion';
declare const initCollapseMotion: (rootCls?: string) => CSSMotionProps;
declare const _SelectPlacements: readonly ["bottomLeft", "bottomRight", "topLeft", "topRight"];
export type SelectCommonPlacement = (typeof _SelectPlacements)[number];
declare const getTransitionName: (rootPrefixCls: string, motion: string, transitionName?: string) => string;
export { getTransitionName };
export default initCollapseMotion;
