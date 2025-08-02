import Panel from './Panel';
import SplitterComp from './Splitter';
export type { SplitterProps } from './interface';
type CompoundedComponent = typeof SplitterComp & {
    Panel: typeof Panel;
};
declare const Splitter: CompoundedComponent;
export default Splitter;
