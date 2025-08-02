"use client";

import omit from "rc-util/es/omit";
import genPurePanel from '../_util/PurePanel';
import Select from '../select';
import RefAutoComplete from './AutoComplete';
const {
  Option
} = Select;
// We don't care debug panel
/* istanbul ignore next */
const PurePanel = genPurePanel(RefAutoComplete, 'dropdownAlign', props => omit(props, ['visible']));
const AutoComplete = RefAutoComplete;
AutoComplete.Option = Option;
AutoComplete._InternalPanelDoNotUseOrYouWillBeFired = PurePanel;
export default AutoComplete;