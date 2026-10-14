const onenet = require('../../utils/onenet');
const format = require('../../utils/format');

const PROP = onenet.PROP;

Page({
  data: {
    online: false,
    lastUpdate: '--',
    led8Mode: 0,
    rgbMode: 0,
    buzzerOn: false,
    busy: false
  },

  onShow: function () {
    this.fetchState();
  },

  /** 读取设备当前状态 */
  fetchState: function () {
    var that = this;
    return onenet
      .getDeviceProps()
      .then(function (list) {
        var snap = format.buildSnapshot(list, PROP);
        that.setData({
          online: true,
          led8Mode: snap.led8Mode,
          rgbMode: snap.rgbMode,
          buzzerOn: snap.buzzerOn,
          lastUpdate: format.formatTime(Date.now())
        });
      })
      .catch(function () {
        that.setData({ online: false });
      });
  },

  /** 点击模式按钮：下发 led8_mode 或 rgb_mode */
  onModeTap: function (e) {
    var that = this;
    var target = e.currentTarget.dataset.target;
    var mode = Number(e.currentTarget.dataset.mode);
    var identifier = target === 'led8' ? PROP.LED8_MODE : PROP.RGB_MODE;
    var key = target === 'led8' ? 'led8Mode' : 'rgbMode';

    if (this.data.busy || this.data[key] === mode) return;

    var patch = {};
    patch[key] = mode;
    patch.busy = true;
    this.setData(patch);
    wx.showLoading({ title: '下发中', mask: true });

    onenet
      .setDeviceProp(identifier, mode)
      .then(function () {
        wx.hideLoading();
        that.setData({ busy: false });
        wx.showToast({ title: '已切换', icon: 'none' });
        setTimeout(function () {
          that.fetchState();
        }, 1500);
      })
      .catch(function (err) {
        wx.hideLoading();
        var revert = {};
        revert[key] = that.data[key] === mode ? 0 : that.data[key];
        revert.busy = false;
        that.setData(revert);
        wx.showToast({ title: (err && err.message) || '下发失败', icon: 'none' });
        that.fetchState();
      });
  },

  /** 蜂鸣器开关，失败时回滚 */
  onBuzzerChange: function (e) {
    var that = this;
    var value = e.detail.value;
    if (this.data.busy) return;

    this.setData({ buzzerOn: value, busy: true });
    wx.showLoading({ title: '下发中', mask: true });

    onenet
      .setDeviceProp(PROP.BUZZER, value)
      .then(function () {
        wx.hideLoading();
        that.setData({ busy: false });
        wx.showToast({ title: value ? '蜂鸣器已开启' : '蜂鸣器已关闭', icon: 'none' });
        setTimeout(function () {
          that.fetchState();
        }, 1500);
      })
      .catch(function (err) {
        wx.hideLoading();
        that.setData({ buzzerOn: !value, busy: false });
        wx.showToast({ title: (err && err.message) || '下发失败', icon: 'none' });
      });
  },

  /** 一键关闭全部灯光与蜂鸣器 */
  onAllOff: function () {
    var that = this;
    if (this.data.busy) return;

    this.setData({ busy: true, led8Mode: 0, rgbMode: 0, buzzerOn: false });
    wx.showLoading({ title: '下发中', mask: true });

    Promise.all([
      onenet.setDeviceProp(PROP.LED8_MODE, 0),
      onenet.setDeviceProp(PROP.RGB_MODE, 0),
      onenet.setDeviceProp(PROP.BUZZER, false)
    ])
      .then(function () {
        wx.hideLoading();
        that.setData({ busy: false });
        wx.showToast({ title: '已全部关闭', icon: 'none' });
        setTimeout(function () {
          that.fetchState();
        }, 1500);
      })
      .catch(function (err) {
        wx.hideLoading();
        that.setData({ busy: false });
        wx.showToast({ title: (err && err.message) || '下发失败', icon: 'none' });
        that.fetchState();
      });
  },

  onRefresh: function () {
    var that = this;
    wx.showLoading({ title: '同步中', mask: true });
    this.fetchState().then(function () {
      wx.hideLoading();
      wx.showToast({ title: that.data.online ? '已同步' : '同步失败', icon: 'none' });
    });
  }
});
