import type { AppProps } from './App';
import App_ from './App';
import useApp from './useApp';
export type { AppProps };
type CompoundedComponent = typeof App_ & {
    useApp: typeof useApp;
};
declare const App: CompoundedComponent;
export default App;
