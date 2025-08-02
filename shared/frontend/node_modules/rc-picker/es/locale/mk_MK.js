import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'mk_MK',
  today: 'Денес',
  now: 'Сега',
  backToToday: 'Назад до денес',
  ok: 'ОК',
  clear: 'Избриши',
  week: 'Недела',
  month: 'Месец',
  year: 'Година',
  timeSelect: 'Избери време',
  dateSelect: 'Избери датум',
  monthSelect: 'Избери месец',
  yearSelect: 'Избери година',
  decadeSelect: 'Избери деценија',
  dateFormat: 'D.M.YYYY',
  dateTimeFormat: 'D.M.YYYY HH:mm:ss',
  previousMonth: 'Претходен месец (PageUp)',
  nextMonth: 'Нареден месец (PageDown)',
  previousYear: 'Претходна година (Control + left)',
  nextYear: 'Наредна година (Control + right)',
  previousDecade: 'Претходна деценија',
  nextDecade: 'Наредна деценија',
  previousCentury: 'Претходен век',
  nextCentury: 'Нареден век'
});
export default locale;