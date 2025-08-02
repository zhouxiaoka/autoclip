import React from 'react';
/**
 * Like `useMemo`, but this hook result will be shared across all instances.
 */
declare function useUniqueMemo<T>(memoFn: () => T, deps: React.DependencyList): T;
export default useUniqueMemo;
