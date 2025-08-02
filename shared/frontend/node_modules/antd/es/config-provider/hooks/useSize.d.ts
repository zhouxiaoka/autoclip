import type { SizeType } from '../SizeContext';
declare const useSize: <T extends string | undefined | number | object>(customSize?: T | ((ctxSize: SizeType) => T)) => T;
export default useSize;
