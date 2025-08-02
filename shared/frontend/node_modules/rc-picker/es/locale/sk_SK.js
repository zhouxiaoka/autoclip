import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'sk_SK',
  today: 'Dnes',
  now: 'Teraz',
  backToToday: 'Späť na dnes',
  ok: 'OK',
  clear: 'Vymazať',
  week: 'Týždeň',
  month: 'Mesiac',
  year: 'Rok',
  timeSelect: 'Vybrať čas',
  dateSelect: 'Vybrať dátum',
  monthSelect: 'Vybrať mesiac',
  yearSelect: 'Vybrať rok',
  decadeSelect: 'Vybrať dekádu',
  dateFormat: 'D.M.YYYY',
  dateTimeFormat: 'D.M.YYYY HH:mm:ss',
  previousMonth: 'Predchádzajúci mesiac (PageUp)',
  nextMonth: 'Nasledujúci mesiac (PageDown)',
  previousYear: 'Predchádzajúci rok (Control + left)',
  nextYear: 'Nasledujúci rok (Control + right)',
  previousDecade: 'Predchádzajúca dekáda',
  nextDecade: 'Nasledujúca dekáda',
  previousCentury: 'Predchádzajúce storočie',
  nextCentury: 'Nasledujúce storočie'
});
export default locale;