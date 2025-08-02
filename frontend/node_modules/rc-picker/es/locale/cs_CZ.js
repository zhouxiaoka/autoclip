import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'cs_CZ',
  today: 'Dnes',
  now: 'Nyní',
  backToToday: 'Zpět na dnešek',
  ok: 'OK',
  clear: 'Vymazat',
  week: 'Týden',
  month: 'Měsíc',
  year: 'Rok',
  timeSelect: 'Vybrat čas',
  dateSelect: 'Vybrat datum',
  monthSelect: 'Vyberte měsíc',
  yearSelect: 'Vyberte rok',
  decadeSelect: 'Vyberte dekádu',
  dateFormat: 'D.M.YYYY',
  dateTimeFormat: 'D.M.YYYY HH:mm:ss',
  previousMonth: 'Předchozí měsíc (PageUp)',
  nextMonth: 'Následující (PageDown)',
  previousYear: 'Předchozí rok (Control + left)',
  nextYear: 'Následující rok (Control + right)',
  previousDecade: 'Předchozí dekáda',
  nextDecade: 'Následující dekáda',
  previousCentury: 'Předchozí století',
  nextCentury: 'Následující století'
});
export default locale;