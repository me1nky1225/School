/**
 * OneNET 平台配置
 *
 * ⚠️ 安全提示：token 属于敏感凭证，请勿将真实 token 公开到代码仓库。
 *    使用前请将下方 productId / deviceName / token 替换为自己在
 *    OneNET 平台创建的产品、设备信息。
 *
 * token 生成方式：
 *   1. OneNET 控制台右上角「访问权限」获取 用户ID / AccessKey
 *   2. 用官方 Token 生成工具（或脚本）填写：
 *        res    = products/{产品ID}/devices/{设备名称}
 *        et     = 过期时间戳（秒）
 *        method = sha1
 *   3. 将生成的完整 token 字符串粘贴到下方 token 字段
 */
module.exports = {
  /** 接口地址 */
  apiBaseUrl: 'https://iot-api.heclouds.com',

  /** 产品 ID */
  productId: 'your_product_id',

  /** 设备名称 */
  deviceName: 'your_device_name',

  /** 鉴权 token（Authorization 请求头） */
  token: 'your_onenet_token',

  /** 默认自动刷新间隔（毫秒） */
  refreshInterval: 5000
};
