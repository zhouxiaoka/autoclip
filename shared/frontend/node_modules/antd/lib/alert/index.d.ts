import InternalAlert from './Alert';
import ErrorBoundary from './ErrorBoundary';
export type { AlertProps } from './Alert';
type CompoundedComponent = typeof InternalAlert & {
    ErrorBoundary: typeof ErrorBoundary;
};
declare const Alert: CompoundedComponent;
export default Alert;
