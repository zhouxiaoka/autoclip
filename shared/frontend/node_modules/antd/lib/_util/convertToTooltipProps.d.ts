import type { ReactNode } from 'react';
import type { TooltipProps } from '../tooltip';
declare function convertToTooltipProps<P extends TooltipProps>(tooltip: P | ReactNode): P | null;
export default convertToTooltipProps;
