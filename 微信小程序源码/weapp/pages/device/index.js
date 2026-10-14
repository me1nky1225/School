const config = require('../../config/onenet');
const onenet = require('../../utils/onenet');
const format = require('../../utils/format');

/** 可选的刷新间隔（秒） */
const INTERVALS = [3, 5, 10, 30];
const LABELS = ['3 秒', '5 秒', '10 秒', '30 秒'];
const DEFAULT_INDEX = 1;

Page({
  data: {
    productId: config.productId,
    deviceName: config.deviceName,
    apiBaseUrl: config.apiBaseUrl,
    intervalOptions: LABELS,
    intervalIndex: DEFAULT_INDEX,
    testing: false,
    result: '',
    resultOk: false
  },

  onLoad: function () {
    var saved = Number(wx.getStorageSync('refresh_interval'));
    if (saved > 0) {
      var index = INTERVALS.indexOf(Math.round(saved / 1000));
      if (index >= 0) {
        this.setData({ intervalIndex: index });
      }
    }
  },

  /** 切换刷新间隔并持久化 */
  onIntervalChange: function (e) {
    var index = Number(e.detail.value);
    var ms = INTERVALS[index] * 1000;

    wx.setStorageSync('refresh_interval', ms);
    getApp().globalData.refreshInterval = ms;

    this.setData({ intervalIndex: index });
    wx.showToast({ title: '已保存', icon: 'success' });
  },

  /** 连接测试 */
  onTest: function () {
    var that = this;
    if (this.data.testing) return;

    this.setData({ testing: true, result: '' });

    onenet
      .getDeviceProps()
      .then(function (list) {
        that.setData({
          testing: false,
          resultOk: true,
          result:
            '连接成功：返回 ' +
            list.length +
            ' 个属性，时间 ' +
            format.formatTime(Date.now())
        });
      })
      .catch(function (err) {
        that.setData({
          testing: false,
          resultOk: false,
          result: '连接失败：' + ((err && err.message) || '未知错误')
        });
      });
  }
});
