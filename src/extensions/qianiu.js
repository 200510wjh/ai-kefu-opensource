/**
 * AI客服助手 - 淘宝千牛内容脚本
 * 注入到千牛工作台，自动捕获客户消息并发送AI回复
 */

(function() {
  'use strict';

  // 配置
  const CONFIG = {
    apiBase: 'http://localhost:8000',
    pollInterval: 2000
  };

  // 状态
  let isEnabled = true;
  let lastMessageCount = 0;

  // 日志
  function log(...args) {
    console.log(`[AI客服-千牛]`, new Date().toLocaleTimeString('zh-CN'), ...args);
  }

  // 发送消息到后端
  async function sendToBackend(data) {
    try {
      const response = await fetch(`${CONFIG.apiBase}/api/webhook/tb_qianiu`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      return await response.json();
    } catch (error) {
      log('发送失败:', error.message);
      return { code: 1, msg: error.message };
    }
  }

  // 获取AI回复
  async function getAIReply(message, userId, context = {}) {
    try {
      const response = await fetch(`${CONFIG.apiBase}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message,
          user_id: userId,
          platform: 'tb_qianiu',
          order_no: context.orderNo,
          goods_info: context.goodsInfo
        })
      });
      const result = await response.json();
      return result;
    } catch (error) {
      log('获取AI回复失败:', error.message);
      return { code: 1, msg: error.message };
    }
  }

  // 提取消息内容
  function extractMessage(element) {
    const result = {
      content: '',
      userId: '',
      orderNo: null,
      goodsInfo: null,
      type: 'text'
    };

    try {
      // 千牛的消息选择器（根据实际页面调整）
      const selectors = [
        '.message-content',
        '.chat-msg-text',
        '.dialog-msg-content',
        '[class*="message-bubble"]',
        '.msg-text'
      ];

      for (const selector of selectors) {
        const msgEl = element.querySelector(selector);
        if (msgEl) {
          result.content = msgEl.innerText.trim();
          break;
        }
      }

      // 提取买家昵称/ID
      const userSelectors = [
        '.buyer-nick',
        '.user-name',
        '[class*="user-info"] .name',
        '.chat-header-title'
      ];

      for (const selector of userSelectors) {
        const userEl = document.querySelector(selector);
        if (userEl) {
          result.userId = userEl.innerText.trim();
          break;
        }
      }

      // 提取订单编号
      const orderPatterns = [
        /订单号[：:]\s*(\d+)/,
        /订单编号[：:]\s*(\d+)/,
        /(\d{10,20})/
      ];

      for (const pattern of orderPatterns) {
        const match = result.content.match(pattern);
        if (match) {
          result.orderNo = match[1];
          break;
        }
      }

      // 检测商品链接
      if (result.content.includes('商品') || result.content.includes('链接') || result.content.includes('看看')) {
        result.goodsInfo = { detected: true, content: result.content };
      }

    } catch (error) {
      log('提取消息失败:', error);
    }

    return result;
  }

  // 检测新消息
  function detectNewMessages() {
    if (!isEnabled) return;

    try {
      // 千牛消息列表选择器
      const selectors = [
        '.chat-list-item',
        '.conversation-item',
        '[class*="chat-record"]',
        '.message-list-item'
      ];

      let messages = [];
      for (const selector of selectors) {
        messages = document.querySelectorAll(selector);
        if (messages.length > 0) break;
      }

      if (messages.length === 0) return;

      // 检查是否有新消息
      if (messages.length > lastMessageCount) {
        const newMessages = Array.from(messages).slice(lastMessageCount);
        
        newMessages.forEach(async (msgElement) => {
          const msgData = extractMessage(msgElement);
          if (msgData.content && msgData.content.length > 1) {
            log('检测到新消息:', msgData.content.substring(0, 50));
            
            // 发送到后端获取AI回复
            const response = await getAIReply(
              msgData.content,
              msgData.userId || 'unknown',
              {
                orderNo: msgData.orderNo,
                goodsInfo: msgData.goodsInfo
              }
            );

            if (response.code === 0 && response.data && response.data.reply) {
              log('AI回复:', response.data.reply.substring(0, 50));
              insertAIResponse(response.data.reply);
            }
          }
        });

        lastMessageCount = messages.length;
      }

    } catch (error) {
      log('检测消息失败:', error);
    }
  }

  // 插入AI回复到输入框
  function insertAIResponse(replyText) {
    try {
      // 千牛输入框选择器
      const inputSelectors = [
        '#chat-input textarea',
        '.msg-input textarea',
        '[class*="chat-input"] textarea',
        '.input-box textarea',
        'textarea[placeholder*="回复"]'
      ];

      let inputElement = null;
      for (const selector of inputSelectors) {
        inputElement = document.querySelector(selector);
        if (inputElement) break;
      }

      if (inputElement) {
        inputElement.focus();
        
        // 插入文本
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
          window.HTMLTextAreaElement.prototype, 'value'
        );

        if (nativeInputValueSetter) {
          nativeInputValueSetter.set.call(inputElement, replyText);
          inputElement.dispatchEvent(new Event('input', { bubbles: true }));
        }
        
        log('已插入AI回复到输入框');
      } else {
        log('未找到输入框元素');
      }

    } catch (error) {
      log('插入回复失败:', error);
    }
  }

  // 监听来自后台的消息
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'toggle') {
      isEnabled = request.enabled;
      log('AI客服已', isEnabled ? '启用' : '禁用');
    }
  });

  // 启动监控
  function startMonitoring() {
    log('开始监控千牛消息...');
    
    // 立即检测一次
    detectNewMessages();
    
    // 定期检测
    setInterval(detectNewMessages, CONFIG.pollInterval);
  }

  // 页面加载完成后启动
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startMonitoring);
  } else {
    startMonitoring();
  }

  // 页面切换时重新检测
  let lastUrl = location.href;
  new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      lastMessageCount = 0;
      log('页面切换，重新检测...');
      setTimeout(detectNewMessages, 1000);
    }
  }).observe(document.body, { subtree: true, childList: true });

})();
