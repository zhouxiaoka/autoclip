import RefAutoComplete from './AutoComplete';
export type { AutoCompleteProps } from './AutoComplete';
declare const Option: import("rc-select/lib/Option").OptionFC;
declare const PurePanel: (props: import("../_util/type").AnyObject) => React.JSX.Element;
type CompoundedComponent = typeof RefAutoComplete & {
    Option: typeof Option;
    _InternalPanelDoNotUseOrYouWillBeFired: typeof PurePanel;
};
declare const AutoComplete: CompoundedComponent;
export default AutoComplete;
