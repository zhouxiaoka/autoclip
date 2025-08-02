import { useEvent } from 'rc-util';
import { isSame } from "../../utils/dateUtil";
/**
 * Merge `disabledDate` with `minDate` & `maxDate`.
 */
export default function useDisabledBoundary(generateConfig, locale, disabledDate, minDate, maxDate) {
  var mergedDisabledDate = useEvent(function (date, info) {
    if (disabledDate && disabledDate(date, info)) {
      return true;
    }
    if (minDate && generateConfig.isAfter(minDate, date) && !isSame(generateConfig, locale, minDate, date, info.type)) {
      return true;
    }
    if (maxDate && generateConfig.isAfter(date, maxDate) && !isSame(generateConfig, locale, maxDate, date, info.type)) {
      return true;
    }
    return false;
  });
  return mergedDisabledDate;
}