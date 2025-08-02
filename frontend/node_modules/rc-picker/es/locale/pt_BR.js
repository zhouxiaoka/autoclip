import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'pt_BR',
  today: 'Hoje',
  now: 'Agora',
  backToToday: 'Voltar para hoje',
  ok: 'OK',
  clear: 'Limpar',
  week: 'Semana',
  month: 'Mês',
  year: 'Ano',
  timeSelect: 'Selecionar hora',
  dateSelect: 'Selecionar data',
  monthSelect: 'Escolher mês',
  yearSelect: 'Escolher ano',
  decadeSelect: 'Escolher década',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  monthBeforeYear: false,
  previousMonth: 'Mês anterior (PageUp)',
  nextMonth: 'Próximo mês (PageDown)',
  previousYear: 'Ano anterior (Control + esquerda)',
  nextYear: 'Próximo ano (Control + direita)',
  previousDecade: 'Década anterior',
  nextDecade: 'Próxima década',
  previousCentury: 'Século anterior',
  nextCentury: 'Próximo século',
  shortWeekDays: ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'],
  shortMonths: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
});
export default locale;