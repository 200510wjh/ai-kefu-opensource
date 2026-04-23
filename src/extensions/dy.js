/**
 * AI客服助手 - 抖店内容脚本
 * 基于实际页面分析的选择器，适配抖店商家后台
 */

(function() {
  'use strict';

  // 配置
  const CONFIG = {
    apiBase: 'http://localhost:8000',
    pollInterval: 2000,
    debug: false
  };

  // 状态
  let isEnabled = true;
  let lastMessageCount = 0;
  let lastMessageContent = '';

  // 日志
  function log(...args) {
    if (CONFIG.debug) {
      console.log(`[AI客服-抖店]`, new Date().toLocaleTimeString('zh-CN'), ...args);
    }
  }

  // 发送消息到后端
  async function sendToBackend(data) {
    try {
      const response = await fetch(`${CONFIG.apiBase}/api/webhook/douyin`, {
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
          platform: 'douyin',
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
      // 抖店消息内容选择器 (来自实际页面分析)
      const contentSelectors = [
        '.message-text',
        '.msg-text',
        '[class*="message-content"]',
        '[class*="msg-bubble"]',
        '.chat-message-content',
        'div[class*="message"][class*="text"]'
      ];

      for (const selector of contentSelectors) {
        const msgEl = element.querySelector(selector);
        if (msgEl) {
          result.content = msgEl.innerText.trim();
          break;
        }
      }

      // 如果没找到，尝试直接获取文本
      if (!result.content) {
        const directText = element.innerText.trim();
        if (directText && directText.length > 0 && directText.length < 5000) {
          result.content = directText;
        }
      }

      // 提取用户ID (买家昵称)
      const userSelectors = [
        '.user-name',
        '.buyer-name',
        '[class*="user-nick"]',
        '[class*="customer-name"]',
        '.chat-header-title'
      ];

      for (const selector of userSelectors) {
        const userEl = document.querySelector(selector);
        if (userEl) {
          result.userId = userEl.innerText.trim();
          break;
        }
      }

      // 检测订单编号
      const orderPatterns = [
        /订单号[：:]\s*(\d+)/,
        /订单编号[：:]\s*(\d+)/,
        /订单\d{10,}/,
        /(\d{10,20})/
      ];

      for (const pattern of orderPatterns) {
        if (result.content) {
          const match = result.content.match(pattern);
          if (match) {
            result.orderNo = match[1] || match[0];
            break;
          }
        }
      }

      // 检测商品链接
      if (result.content && (result.content.includes('商品') || result.content.includes('链接') || result.content.includes('看看'))) {
        result.goodsInfo = { detected: true, content: result.content.substring(0, 100) };
      }

    } catch (error) {
      log('提取消息失败:', error);
    }

    return result;
  }

  // 检测新消息 - 使用抖店特定的选择器
  function detectNewMessages() {
    if (!isEnabled) return;

    try {
      // 抖店会话列表选择器 (来自实际页面)
      const conversationSelectors = [
        'span[data-qa-id="qa-conversation"]',
        '[data-qa-i*="conversation"]',
        '.conversation-item',
        '[class*="chat-list"] [class*="item"]',
        '[class*="message-list"] [class*="item"]',
        '.im-conversation-item',
        '[class*="session-item"]'
      ];

      let conversations = [];
      for (const selector of conversationSelectors) {
        try {
          conversations = document.querySelectorAll(selector);
          if (conversations.length > 0) {
            log('找到会话数:', conversations.length, '使用选择器:', selector);
            break;
          }
        } catch (e) {
          // 无效选择器，继续
        }
      }

      if (conversations.length === 0) {
        // 尝试通用的消息列表
        const fallbackSelectors = ['[class*="message"]', '[class*="chat"]'].flatMap(s => {
          try {
            return Array.from(document.querySelectorAll(s));
          } catch {
            return [];
          }
        }).filter(el => {
          const text = el.innerText || '';
          return text.length > 1 && text.length < 1000;
        });
        
        if (fallbackSelectors.length > 0) {
          log('使用fallback选择器找到元素:', fallbackSelectors.length);
        }
        return;
      }

      // 获取当前选中的会话的最新消息
      const latestSelector = conversationSelectors[0];
      const latestConversations = document.querySelectorAll(latestSelector);
      
      if (latestConversations.length > 0) {
        // 遍历会话找最新消息
        latestConversations.forEach(conv => {
          const msgData = extractMessage(conv);
          if (msgData.content && msgData.content !== lastMessageContent) {
            log('检测到新消息:', msgData.content.substring(0, 50));
            
            // 发送到后端获取AI回复
            getAIReply(msgData.content, msgData.userId || 'unknown', {
              orderNo: msgData.orderNo,
              goodsInfo: msgData.goodsInfo
            }).then(response => {
              if (response.code === 0 && response.data && response.data.reply) {
                log('AI回复:', response.data.reply.substring(0, 50));
                insertAIResponse(response.data.reply);
                lastMessageContent = msgData.content;
              }
            });
          }
        });
      }

    } catch (error) {
      log('检测消息失败:', error);
    }
  }

  // 插入AI回复到输入框 - 使用抖店特定选择器
  function insertAIResponse(replyText) {
    try {
      // 抖店输入框选择器 (来自实际页面)
      const inputSelectors = [
        'span.auxo-sp-input',  // 抖店官方选择器
        'textarea[data-qa-id="qa-send-message"]',
        'textarea[class*="input"]',
        '[data-qa-i*="input"]',
        'textarea[class*="message-input"]',
        'textarea[class*="chat-input"]',
        '[contenteditable="true"]'
      ];

      let inputElement = null;
      for (const selector of inputSelectors) {
        try {
          inputElement = document.querySelector(selector);
          if (inputElement) {
            log('找到输入框:', selector);
            break;
          }
        } catch (e) {
          // 无效选择器
        }
      }

      if (inputElement) {
        inputElement.focus();
        
        // 设置值
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
          window.HTMLTextAreaElement.prototype, 'value'
        ) || Object.getOwnPropertyDescriptor(
          window.HTMLDivElement.prototype, 'innerText'
        );

        if (nativeInputValueSetter) {
          nativeInputValueSetter.set.call(inputElement, replyText);
          inputElement.dispatchEvent(new Event('input', { bubbles: true }));
        }
        
        log('已插入AI回复');
        
        // 自动点击发送按钮
        setTimeout(() => {
          const sendButtonSelectors = [
            '[data-qa-id="qa-send-message"]',
            '[class*="send-button"]',
            '[class*="submit"]',
            'button[class*="send"]'
          ];
          
          for (const selector of sendButtonSelectors) {
            const sendBtn = document.querySelector(selector);
            if (sendBtn) {
              sendBtn.click();
              log('已点击发送按钮');
              break;
            }
          }
        }, 100);
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
    if (request.type === 'get-status') {
      sendResponse({ enabled: isEnabled });
    }
  });

  // 启动监控
  function startMonitoring() {
    log('开始监控抖店消息...');
    
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
      lastMessageContent = '';
      log('页面切换，重新检测...');
      setTimeout(detectNewMessages, 2000);
    }
  }).observe(document.body, { subtree: true, childList: true });

})();
