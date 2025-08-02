import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'pt_PT',
  today: 'Hoje',
  now: 'Agora',
  backToToday: 'Hoje',
  ok: 'OK',
  clear: 'Limpar',
  week: 'Semana',
  month: 'Mês',
  year: 'Ano',
  timeSelect: 'Selecionar hora',
  dateSelect: 'Selecionar data',
  monthSelect: 'Selecionar mês',
  yearSelect: 'Selecionar ano',
  decadeSelect: 'Selecionar década',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'Mês anterior (PageUp)',
  nextMonth: 'Mês seguinte (PageDown)',
  previousYear: 'Ano anterior (Control + left)',
  nextYear: 'Ano seguinte (Control + right)',
  previousDecade: 'Década anterior',
  nextDecade: 'Década seguinte',
  previousCentury: 'Século anterior',
  nextCentury: 'Século seguinte',
  shortWeekDays: ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'],
  shortMonths: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
});
export default locale;