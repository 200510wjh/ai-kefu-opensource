/**
 * AI客服助手 - 浏览器插件后台脚本
 * 负责消息中转和状态管理
 */

// 后端API地址
const API_BASE = 'http://localhost:8000';

// 连接状态
let isConnected = false;
let connectionCheckInterval = null;

// 初始化
async function initialize() {
  console.log('[AI客服] 插件初始化中...');
  await checkConnection();
  startConnectionMonitor();
}

// 检查后端连接状态
async function checkConnection() {
  try {
    const response = await fetch(`${API_BASE}/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (response.ok) {
      if (!isConnected) {
        isConnected = true;
        updateBadge('connected');
        console.log('[AI客服] 已连接到后端服务');
      }
      return true;
    }
  } catch (error) {
    if (isConnected) {
      isConnected = false;
      updateBadge('disconnected');
      console.log('[AI客服] 后端连接断开:', error.message);
    }
    return false;
  }
}

// 启动连接监控
function startConnectionMonitor() {
  // 每30秒检查一次连接
  connectionCheckInterval = setInterval(checkConnection, 30000);
}

// 更新扩展图标徽章
function updateBadge(status) {
  const iconPath = status === 'connected' 
    ? 'icons/icon-green.png' 
    : 'icons/icon-red.png';
  
  chrome.action.setIcon({ path: iconPath });
  chrome.action.setBadgeText({ text: status === 'connected' ? '✓' : '!' });
}

// 发送消息到后端
async function sendToBackend(messageData) {
  try {
    const response = await fetch(`${API_BASE}/api/webhook/douyin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(messageData)
    });
    
    return await response.json();
  } catch (error) {
    console.error('[AI客服] 发送消息失败:', error);
    return { code: 1, msg: error.message };
  }
}

// 获取AI回复
async function getAIReply(userMessage, userId, context = {}) {
  try {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: userMessage,
        user_id: userId,
        platform: 'douyin',
        order_no: context.orderNo,
        goods_info: context.goodsInfo
      })
    });
    
    const result = await response.json();
    return result;
  } catch (error) {
    console.error('[AI客服] 获取AI回复失败:', error);
    return { code: 1, msg: error.message };
  }
}

// 监听来自content script的消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('[AI客服] 收到消息:', request.type);
  
  switch (request.type) {
    case 'new-message':
      // 处理新消息
      handleNewMessage(request.data).then(sendResponse);
      return true; // 异步响应
      
    case 'get-status':
      sendResponse({ connected: isConnected });
      return false;
      
    case 'get-stats':
      getStats().then(sendResponse);
      return true;
      
    default:
      console.warn('[AI客服] 未知消息类型:', request.type);
      return false;
  }
});

// 处理新消息
async function handleNewMessage(data) {
  // 存储消息
  console.log('[AI客服] 收到客户消息:', data.content);
  
  // 获取AI回复
  const aiReply = await getAIReply(
    data.content,
    data.userId,
    { orderNo: data.orderNo, goodsInfo: data.goodsInfo }
  );
  
  if (aiReply.code === 0) {
    return {
      success: true,
      reply: aiReply.data.reply,
      messageId: aiReply.data.message_id
    };
  } else {
    return { success: false, error: aiReply.msg };
  }
}

// 获取统计数据
async function getStats() {
  try {
    const response = await fetch(`${API_BASE}/api/stats`);
    return await response.json();
  } catch (error) {
    return { code: 1, msg: error.message };
  }
}

// 插件安装或更新时执行
chrome.runtime.onInstalled.addListener((details) => {
  console.log('[AI客服] 插件已安装/更新:', details.reason);
  initialize();
});

// 启动
initialize();
