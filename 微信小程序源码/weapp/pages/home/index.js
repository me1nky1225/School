const onenet = require('../../utils/onenet');
const format = require('../../utils/format');

const PROP = onenet.PROP;

Page({
  data: {
    online: false,
    error: '',
    lastUpdate: '--',
    snapshot: {
      temperature: '--',
      humidity: '--',
      distance: '--',
      lightText: '--',
      lightRaw: '--',
      led8Mode: 0,
      rgbMode: 0,
      buzzerOn: false
    },
    led8ModeText: '--',
    rgbModeText: '--'
  },

  onLoad: function () {
    this.fetchData();
  },

  onShow: function () {
    this.startTimer();
  },

  onHide: function () {
    this.stopTimer();
  },

  onUnload: function () {
    this.stopTimer();
  },

  onPullDownRefresh: function () {
    this.fetchData().then(function () {
      wx.stopPullDownRefresh();
    });
  },

  /** 按设置的间隔自动轮询 */
  startTimer: function () {
    var that = this;
    this.stopTimer();
    var interval = getApp().globalData.refreshInterval || 5000;
    this.timer = setInterval(function () {
      that.fetchData();
    }, interval);
  },

  stopTimer: function () {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  },

  /** 拉取设备最新属性 */
  fetchData: function () {
    var that = this;
    return onenet
      .getDeviceProps()
      .then(function (list) {
        var snapshot = format.buildSnapshot(list, PROP);
        that.setData({
          online: true,
          error: '',
          lastUpdate: format.formatTime(Date.now()),
          snapshot: snapshot,
          led8ModeText: format.led8ModeText(snapshot.led8Mode),
          rgbModeText: format.rgbModeText(snapshot.rgbMode)
        });
      })
      .catch(function (err) {
        that.setData({
          online: false,
          error: (err && err.message) || '请求失败，请检查网络'
        });
      });
  },

  onRetry: function () {
    wx.showLoading({ title: '加载中', mask: true });
    this.fetchData().then(function () {
      wx.hideLoading();
    });
  }
});
