/**
 * AI客服助手 - 拼多多内容脚本
 * 注入到拼多多商家后台，自动捕获客户消息并发送AI回复
 */

(function() {
  'use strict';

  const CONFIG = {
    apiBase: 'http://localhost:8000',
    pollInterval: 2000,
    debug: false
  };

  let isEnabled = true;
  let lastMessageContent = '';

  function log(...args) {
    if (CONFIG.debug) {
      console.log(`[AI客服-拼多多]`, new Date().toLocaleTimeString('zh-CN'), ...args);
    }
  }

  async function getAIReply(message, userId) {
    try {
      const response = await fetch(`${CONFIG.apiBase}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message,
          user_id: userId,
          platform: 'pinduoduo'
        })
      });
      return await response.json();
    } catch (error) {
      log('获取AI回复失败:', error.message);
      return { code: 1, msg: error.message };
    }
  }

  function extractMessage(element) {
    const result = { content: '', userId: '', orderNo: null };
    
    try {
      // 拼多多消息选择器
      const selectors = [
        '.message-text',
        '.msg-content',
        '[class*="message-content"]',
        '[class*="chat-message"]',
        '.chat-bubble-text',
        '[class*="dialog-msg"]'
      ];

      for (const selector of selectors) {
        const msgEl = element.querySelector(selector);
        if (msgEl) {
          result.content = msgEl.innerText.trim();
          break;
        }
      }

      if (!result.content) {
        const text = element.innerText.trim();
        if (text && text.length < 5000) {
          result.content = text;
        }
      }

      // 订单检测
      const orderMatch = result.content.match(/订单[号:]?\s*(\d+)/);
      if (orderMatch) result.orderNo = orderMatch[1];

    } catch (error) {
      log('提取消息失败:', error);
    }
    
    return result;
  }

  function detectNewMessages() {
    if (!isEnabled) return;

    try {
      // 拼多多会话列表选择器
      const selectors = [
        '[class*="conversation-item"]',
        '[class*="chat-list"] [class*="item"]',
        '[class*="message-list"] [class*="item"]',
        '[class*="session-item"]',
        '.pdd-conversation-item'
      ];

      let conversations = [];
      for (const selector of selectors) {
        try {
          conversations = document.querySelectorAll(selector);
          if (conversations.length > 0) {
            log('找到会话:', conversations.length, selector);
            break;
          }
        } catch (e) {}
      }

      if (conversations.length === 0) return;

      conversations.forEach(conv => {
        const msgData = extractMessage(conv);
        if (msgData.content && msgData.content !== lastMessageContent) {
          log('检测到消息:', msgData.content.substring(0, 50));
          
          getAIReply(msgData.content, msgData.userId || 'unknown').then(response => {
            if (response.code === 0 && response.data?.reply) {
              log('AI回复:', response.data.reply.substring(0, 50));
              insertAIResponse(response.data.reply);
              lastMessageContent = msgData.content;
            }
          });
        }
      });

    } catch (error) {
      log('检测失败:', error);
    }
  }

  function insertAIResponse(replyText) {
    try {
      const inputSelectors = [
        'textarea[class*="input"]',
        'textarea[class*="message"]',
        '[class*="input"] textarea',
        '[contenteditable="true"]',
        '#chat-input textarea'
      ];

      let inputElement = null;
      for (const selector of inputSelectors) {
        inputElement = document.querySelector(selector);
        if (inputElement) break;
      }

      if (inputElement) {
        inputElement.focus();
        
        const nativeSetter = Object.getOwnPropertyDescriptor(
          window.HTMLTextAreaElement.prototype, 'value'
        );
        
        if (nativeSetter) {
          nativeSetter.set.call(inputElement, replyText);
          inputElement.dispatchEvent(new Event('input', { bubbles: true }));
        }
        
        log('已插入回复');
        
        setTimeout(() => {
          const sendBtn = document.querySelector('[class*="send"], [class*="submit"] button, .send-btn, .pdd-send-btn');
          if (sendBtn) {
            sendBtn.click();
            log('已发送');
          }
        }, 100);
      }
    } catch (error) {
      log('插入失败:', error);
    }
  }

  chrome.runtime.onMessage.addListener((request) => {
    if (request.type === 'toggle') {
      isEnabled = request.enabled;
      log('已', isEnabled ? '启用' : '禁用');
    }
  });

  function startMonitoring() {
    log('开始监控拼多多消息...');
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
      lastMessageContent = '';
      setTimeout(detectNewMessages, 2000);
    }
  }).observe(document.body, { subtree: true, childList: true });

})();
