(function() {
  'use strict';

  const CONFIG = {
    apiBase: 'http://localhost:8000',
    pollInterval: 2000,
    debug: false
  };

  let isEnabled = true;
  let lastMessages = new Map();
  let processedIds = new Set();

  function log(...args) {
    if (CONFIG.debug) {
      console.log(`[AI客服-闲鱼]`, new Date().toLocaleTimeString('zh-CN'), ...args);
    }
  }

  async function sendToBackend(data) {
    try {
      const response = await fetch(`${CONFIG.apiBase}/api/webhook/xianyu`, {
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

  async function getAIReply(message, userId, context = {}) {
    try {
      const response = await fetch(`${CONFIG.apiBase}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message,
          user_id: userId,
          platform: 'xianyu',
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

  function extractMessage(element) {
    const result = {
      id: '',
      content: '',
      userId: '',
      userName: '',
      goodsInfo: null,
      timestamp: null
    };

    try {
      const contentSelectors = [
        '.message-content',
        '.msg-bubble',
        '.chat-msg-text',
        '[class*="message-content"]',
        '[class*="msg-content"]',
        '.message-text'
      ];

      for (const selector of contentSelectors) {
        const msgEl = element.querySelector(selector);
        if (msgEl) {
          result.content = msgEl.innerText.trim();
          break;
        }
      }

      if (!result.content) {
        const directText = element.innerText.trim();
        if (directText && directText.length > 0 && directText.length < 5000) {
          result.content = directText;
        }
      }

      result.id = element.dataset.msgId || element.id || Date.now().toString();
      result.timestamp = Date.now();

      const userSelectors = [
        '.user-name',
        '.nick-name',
        '.seller-name',
        '[class*="user-name"]',
        '[class*="nick"]'
      ];

      for (const selector of userSelectors) {
        const userEl = element.querySelector(selector) || document.querySelector(selector);
        if (userEl) {
          result.userName = userEl.innerText.trim();
          break;
        }
      }

      const buyerSelectors = [
        '.buyer-name',
        '.im-buyer-name',
        '.chat-buyer'
      ];
      for (const selector of buyerSelectors) {
        const buyerEl = document.querySelector(selector);
        if (buyerEl) {
          result.userId = buyerEl.dataset.userId || buyerEl.innerText.trim();
          break;
        }
      }

      if (!result.userId) {
        result.userId = result.userName || 'buyer_' + Math.random().toString(36).substr(2, 8);
      }

      const goodsPatterns = [
        /商品[：:]\s*(.+)/,
        /链接[：:]\s*(https?:\/\/[^\s]+)/,
        /(闲鱼链接|宝贝链接)[：:]\s*(https?:\/\/[^\s]+)/
      ];

      for (const pattern of goodsPatterns) {
        const match = result.content.match(pattern);
        if (match) {
          result.goodsInfo = { type: 'goods_link', content: match[1] || match[2] };
          break;
        }
      }

    } catch (error) {
      log('提取消息失败:', error);
    }

    return result;
  }

  function detectNewMessages() {
    if (!isEnabled) return;

    try {
      const conversationSelectors = [
        '.message-list-item',
        '.chat-item',
        '[class*="message-item"]',
        '[class*="chat-item"]',
        '.im-conversation-item',
        '.conversation-item',
        '[class*="session-item"]'
      ];

      let conversations = [];
      for (const selector of conversationSelectors) {
        try {
          conversations = document.querySelectorAll(selector);
          if (conversations.length > 0) {
            log('找到会话数:', conversations.length, '选择器:', selector);
            break;
          }
        } catch (e) {}
      }

      if (conversations.length === 0) {
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
          log('使用fallback找到元素:', fallbackSelectors.length);
        }
        return;
      }

      conversations.forEach(conv => {
        const msgData = extractMessage(conv);

        if (msgData.content && !processedIds.has(msgData.id)) {
          log('检测到新消息:', msgData.content.substring(0, 50));

          sendToBackend({
            type: 'xianyu_message',
            user_id: msgData.userId,
            user_name: msgData.userName,
            content: msgData.content,
            goods_info: msgData.goodsInfo,
            timestamp: msgData.timestamp
          }).then(response => {
            if (response.code === 0 && response.data && response.data.auto_reply) {
              log('AI回复:', response.data.auto_reply.substring(0, 50));
              insertAIResponse(response.data.auto_reply);
            }
          });

          processedIds.add(msgData.id);
          if (processedIds.size > 1000) {
            const arr = Array.from(processedIds);
            processedIds = new Set(arr.slice(-500));
          }
        }
      });

    } catch (error) {
      log('检测消息失败:', error);
    }
  }

  function insertAIResponse(replyText) {
    try {
      const inputSelectors = [
        'textarea[class*="input"]',
        'textarea[class*="message"]',
        'textarea[class*="chat"]',
        'textarea[placeholder*="输入"]',
        'textarea[placeholder*="回复"]',
        'textarea[placeholder*="消息"]',
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
        } catch (e) {}
      }

      if (!inputElement) {
        inputElement = document.querySelector('textarea');
      }

      if (inputElement) {
        inputElement.focus();

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

        setTimeout(() => {
          const sendButtonSelectors = [
            'button[class*="send"]',
            'button[class*="submit"]',
            '[class*="send-btn"]',
            '[class*="submit-btn"]',
            'button:enabled'
          ];

          for (const selector of sendButtonSelectors) {
            const sendBtn = document.querySelector(selector);
            if (sendBtn && !sendBtn.disabled) {
              const btnText = sendBtn.innerText || '';
              if (btnText.includes('发送') || btnText.includes('回复') || btnText.includes('send')) {
                sendBtn.click();
                log('已点击发送按钮');
                break;
              }
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

  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'toggle') {
      isEnabled = request.enabled;
      log('AI客服已', isEnabled ? '启用' : '禁用');
    }
    if (request.type === 'get-status') {
      sendResponse({ enabled: isEnabled });
    }
    if (request.type === 'manual-reply') {
      insertAIResponse(request.reply);
    }
  });

  function startMonitoring() {
    log('开始监控闲鱼消息...');
    detectNewMessages();
    setInterval(detectNewMessages, CONFIG.pollInterval);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startMonitoring);
  } else {
    startMonitoring();
  }

  let lastUrl = location.href;
  new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      processedIds.clear();
      log('页面切换，重新检测...');
      setTimeout(detectNewMessages, 2000);
    }
  }).observe(document.body, { subtree: true, childList: true });

})();
