/**
 * OneNET 开放 API 封装
 * 仅依赖 wx.request，无需任何第三方库
 */
const config = require('../config/onenet');

/** 属性标识符，与 ESP32 端物模型保持一致 */
const PROP = {
  TEMP: 'temp_value',
  HUMIDITY: 'humidity_value',
  DISTANCE: 'distance_value',
  LIGHT: 'light_value',
  LED: 'led_switch',
  LED8_MODE: 'led8_mode',
  RGB_MODE: 'rgb_mode',
  BUZZER: 'buzzer_switch'
};

/** 统一发起请求 */
function request(path, method, data) {
  return new Promise(function (resolve, reject) {
    wx.request({
      url: config.apiBaseUrl + path,
      method: method,
      data: data,
      header: {
        Authorization: config.token,
        'Content-Type': 'application/json'
      },
      success: function (res) {
        if (res.statusCode !== 200) {
          console.error('[OneNET] HTTP 状态异常:', res.statusCode);
          reject(new Error('HTTP ' + res.statusCode));
          return;
        }
        if (!res.data || res.data.code !== 0) {
          console.error('[OneNET] 接口返回异常:', res.data);
          reject(new Error((res.data && res.data.msg) || '接口返回异常'));
          return;
        }
        resolve(res.data);
      },
      fail: function (err) {
        console.error('[OneNET] 请求失败:', err);
        reject(err);
      }
    });
  });
}

/**
 * 查询设备最新属性
 * @returns {Promise<Array>} 属性数组 [{ identifier, value, time }]
 */
function getDeviceProps() {
  var path =
    '/thingmodel/query-device-property?product_id=' +
    encodeURIComponent(config.productId) +
    '&device_name=' +
    encodeURIComponent(config.deviceName);

  return request(path, 'GET').then(function (res) {
    return Array.isArray(res.data) ? res.data : [];
  });
}

/**
 * 下发设备属性
 * @param {string} identifier 属性标识符
 * @param {boolean|number} value 属性值（开关用 bool，模式用 0/1/2）
 */
function setDeviceProp(identifier, value) {
  var params = {};
  params[identifier] = value;

  return request('/thingmodel/set-device-property', 'POST', {
    product_id: config.productId,
    device_name: config.deviceName,
    params: params
  });
}

module.exports = {
  PROP: PROP,
  getDeviceProps: getDeviceProps,
  setDeviceProp: setDeviceProp
};
