import type { ScreenMap } from '../../_util/responsiveObserver';
declare function useBreakpoint(refreshOnChange: boolean, defaultScreens: null): ScreenMap | null;
declare function useBreakpoint(refreshOnChange?: boolean, defaultScreens?: ScreenMap): ScreenMap;
export default useBreakpoint;
