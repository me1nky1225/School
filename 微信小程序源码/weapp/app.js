App({
  globalData: {
    /** 自动刷新间隔（毫秒），在「设备」页可调整 */
    refreshInterval: 5000
  },

  onLaunch: function () {
    var saved = wx.getStorageSync('refresh_interval');
    if (saved) {
      this.globalData.refreshInterval = saved;
    }
  }
});
