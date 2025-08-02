import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'sr_RS',
  today: 'Danas',
  now: 'Sada',
  backToToday: 'Vrati se na danas',
  ok: 'U redu',
  clear: 'Obriši',
  week: 'Nedelja',
  month: 'Mesec',
  year: 'Godina',
  timeSelect: 'Izaberi vreme',
  dateSelect: 'Izaberi datum',
  monthSelect: 'Izaberi mesec',
  yearSelect: 'Izaberi godinu',
  decadeSelect: 'Izaberi deceniju',
  dateFormat: 'DD.MM.YYYY',
  dateTimeFormat: 'DD.MM.YYYY HH:mm:ss',
  previousMonth: 'Prethodni mesec (PageUp)',
  nextMonth: 'Sledeći mesec (PageDown)',
  previousYear: 'Prethodna godina (Control + left)',
  nextYear: 'Sledeća godina (Control + right)',
  previousDecade: 'Prethodna decenija',
  nextDecade: 'Sledeća decenija',
  previousCentury: 'Prethodni vek',
  nextCentury: 'Sledeći vek'
});
export default locale;