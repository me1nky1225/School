/**
 * 数据格式化与快照构建工具
 */

/** 8 路 LED 模式文案 */
function led8ModeText(mode) {
  return ['已关闭', '流水灯', '闪烁'][mode] || '未知';
}

/** WS2812B 幻彩灯模式文案 */
function rgbModeText(mode) {
  return ['已关闭', '呼吸灯', '跑马灯'][mode] || '未知';
}

/** 从属性数组中取指定标识符的值 */
function getValue(list, identifier) {
  for (var i = 0; i < list.length; i++) {
    if (list[i].identifier === identifier) {
      return String(list[i].value);
    }
  }
  return '';
}

/** 字符串转布尔 */
function toBool(value) {
  return value === 'true' || value === '1';
}

/** 字符串转数字 */
function toNumber(value, fallback) {
  var num = Number(value);
  return isFinite(num) ? num : fallback;
}

/** 光照 ADC 原始值转等级文案（值越小越亮） */
function lightText(raw) {
  if (raw >= 3000) return '昏暗';
  if (raw >= 2000) return '柔和';
  if (raw >= 1000) return '明亮';
  return '强光';
}

/** 时间戳格式化为 HH:mm:ss */
function formatTime(ts) {
  if (!ts) return '--';
  var d = new Date(ts);
  function pad(n) {
    return n < 10 ? '0' + n : '' + n;
  }
  return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
}

/**
 * 将 OneNET 属性数组归一化为页面展示快照
 * @param {Array} list 属性数组
 * @param {object} prop 属性标识符常量
 */
function buildSnapshot(list, prop) {
  var lightRawText = getValue(list, prop.LIGHT);
  var raw = toNumber(lightRawText, 0);
  return {
    temperature: getValue(list, prop.TEMP) || '--',
    humidity: getValue(list, prop.HUMIDITY) || '--',
    distance: getValue(list, prop.DISTANCE) || '--',
    lightRaw: lightRawText === '' ? '--' : raw,
    lightText: lightRawText === '' ? '--' : lightText(raw),
    ledOn: toBool(getValue(list, prop.LED)),
    led8Mode: toNumber(getValue(list, prop.LED8_MODE), 0),
    rgbMode: toNumber(getValue(list, prop.RGB_MODE), 0),
    buzzerOn: toBool(getValue(list, prop.BUZZER))
  };
}

module.exports = {
  getValue: getValue,
  toBool: toBool,
  toNumber: toNumber,
  lightText: lightText,
  led8ModeText: led8ModeText,
  rgbModeText: rgbModeText,
  formatTime: formatTime,
  buildSnapshot: buildSnapshot
};
