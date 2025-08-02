"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.STEP_START = exports.STEP_PREPARED = exports.STEP_PREPARE = exports.STEP_NONE = exports.STEP_ACTIVE = exports.STEP_ACTIVATED = exports.STATUS_NONE = exports.STATUS_LEAVE = exports.STATUS_ENTER = exports.STATUS_APPEAR = void 0;
var STATUS_NONE = exports.STATUS_NONE = 'none';
var STATUS_APPEAR = exports.STATUS_APPEAR = 'appear';
var STATUS_ENTER = exports.STATUS_ENTER = 'enter';
var STATUS_LEAVE = exports.STATUS_LEAVE = 'leave';
var STEP_NONE = exports.STEP_NONE = 'none';
var STEP_PREPARE = exports.STEP_PREPARE = 'prepare';
var STEP_START = exports.STEP_START = 'start';
var STEP_ACTIVE = exports.STEP_ACTIVE = 'active';
var STEP_ACTIVATED = exports.STEP_ACTIVATED = 'end';
/**
 * Used for disabled motion case.
 * Prepare stage will still work but start & active will be skipped.
 */
var STEP_PREPARED = exports.STEP_PREPARED = 'prepared';