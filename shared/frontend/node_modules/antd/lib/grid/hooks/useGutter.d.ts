import type { ScreenMap } from '../../_util/responsiveObserver';
import type { RowProps } from '../row';
type Gap = number | undefined;
export default function useGutter(gutter: RowProps['gutter'], screens: ScreenMap | null): [Gap, Gap];
export {};
