import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'et_EE',
  today: 'Täna',
  now: 'Praegu',
  backToToday: 'Tagasi tänase juurde',
  ok: 'OK',
  clear: 'Tühista',
  week: 'Nädal',
  month: 'Kuu',
  year: 'Aasta',
  timeSelect: 'Vali aeg',
  dateSelect: 'Vali kuupäev',
  monthSelect: 'Vali kuu',
  yearSelect: 'Vali aasta',
  decadeSelect: 'Vali dekaad',
  dateFormat: 'D.M.YYYY',
  dateTimeFormat: 'D.M.YYYY HH:mm:ss',
  previousMonth: 'Eelmine kuu (PageUp)',
  nextMonth: 'Järgmine kuu (PageDown)',
  previousYear: 'Eelmine aasta (Control + left)',
  nextYear: 'Järgmine aasta (Control + right)',
  previousDecade: 'Eelmine dekaad',
  nextDecade: 'Järgmine dekaad',
  previousCentury: 'Eelmine sajand',
  nextCentury: 'Järgmine sajand'
});
export default locale;