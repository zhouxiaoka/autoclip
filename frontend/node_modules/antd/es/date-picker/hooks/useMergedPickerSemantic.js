import * as React from 'react';
import cls from 'classnames';
import useMergeSemantic from '../../_util/hooks/useMergeSemantic';
import { useComponentConfig } from '../../config-provider/context';
const useMergedPickerSemantic = (pickerType, classNames, styles, popupClassName, popupStyle) => {
  const {
    classNames: contextClassNames,
    styles: contextStyles
  } = useComponentConfig(pickerType);
  const [mergedClassNames, mergedStyles] = useMergeSemantic([contextClassNames, classNames], [contextStyles, styles], {
    popup: {
      _default: 'root'
    }
  });
  return React.useMemo(() => {
    var _a, _b;
    // ClassNames
    const filledClassNames = Object.assign(Object.assign({}, mergedClassNames), {
      popup: Object.assign(Object.assign({}, mergedClassNames.popup), {
        root: cls((_a = mergedClassNames.popup) === null || _a === void 0 ? void 0 : _a.root, popupClassName)
      })
    });
    // Styles
    const filledStyles = Object.assign(Object.assign({}, mergedStyles), {
      popup: Object.assign(Object.assign({}, mergedStyles.popup), {
        root: Object.assign(Object.assign({}, (_b = mergedStyles.popup) === null || _b === void 0 ? void 0 : _b.root), popupStyle)
      })
    });
    // Return
    return [filledClassNames, filledStyles];
  }, [mergedClassNames, mergedStyles, popupClassName, popupStyle]);
};
export default useMergedPickerSemantic;