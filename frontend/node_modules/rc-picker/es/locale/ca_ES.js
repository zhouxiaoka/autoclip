import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'ca_ES',
  today: 'Avui',
  now: 'Ara',
  backToToday: 'Tornar a avui',
  ok: 'Acceptar',
  clear: 'Netejar',
  week: 'Setmana',
  month: 'Mes',
  year: 'Any',
  timeSelect: 'Seleccionar hora',
  dateSelect: 'Seleccionar data',
  monthSelect: 'Escollir un mes',
  yearSelect: 'Escollir un any',
  decadeSelect: 'Escollir una dècada',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'Mes anterior (PageUp)',
  nextMonth: 'Mes següent (PageDown)',
  previousYear: 'Any anterior (Control + left)',
  nextYear: 'Mes següent (Control + right)',
  previousDecade: 'Dècada anterior',
  nextDecade: 'Dècada següent',
  previousCentury: 'Segle anterior',
  nextCentury: 'Segle següent'
});
export default locale;