// ==UserScript==
// @name         Cursor试用生成绑卡自动填写
// @namespace    http://tampermonkey.net/
// @version      2.6.0
// @description  自动填写 Cursor 试用页面的支付信息，支付失败自动重试
// @author       Yan
// @match        https://checkout.stripe.com/c/pay/*
// @match        https://www.google.com/*
// @match        https://www.baidu.com/*
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_addStyle
// @grant        GM_registerMenuCommand
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

    // ===== 全局状态控制 =====
    let isRunning = false; // 是否正在执行
    let shouldStop = false; // 是否应该停止

    // ===== 添加CSS样式 =====
    const style = document.createElement('style');
    style.textContent = `
        @keyframes cursor-pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        @keyframes cursor-spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        
        @keyframes cursor-fade-in {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        #cursor-auto-fill-container * {
            box-sizing: border-box !important;
        }
        
        #cursor-auto-fill-panel {
            position: fixed !important;
            top: 24px !important;
            right: 24px !important;
            max-width: 420px !important;
            min-width: 360px !important;
            width: auto !important;
            background: #ffffff !important;
            border-radius: 20px !important;
            box-shadow: 0 24px 48px rgba(0, 0, 0, 0.1), 0 0 0 1px rgba(0, 0, 0, 0.05) !important;
            z-index: 2147483647 !important;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif !important;
            overflow: visible !important;
            animation: cursor-fade-in 0.4s ease !important;
        }
        
        #cursor-auto-fill-header {
            background: #ffffff !important;
            padding: 24px !important;
            color: #000000 !important;
            border-bottom: 1px solid #f0f0f0 !important;
        }
        
        #cursor-auto-fill-header-row {
            display: flex !important;
            justify-content: space-between !important;
            align-items: center !important;·
        }
        
        #cursor-auto-fill-header-title {
            font-size: 20px !important;
            font-weight: 700 !important;
            color: #000000 !important;
            letter-spacing: -0.5px !important;
        }
        
        #cursor-auto-fill-toggle {
            background: #f5f5f5 !important;
            border: none !important;
            color: #666 !important;
            width: 36px !important;
            height: 36px !important;
            border-radius: 10px !important;
            cursor: pointer !important;
            font-size: 22px !important;
            line-height: 1 !important;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }
        
        #cursor-auto-fill-toggle:hover {
            background: #e8e8e8 !important;
            transform: scale(1.05) !important;
        }
        
        #cursor-auto-fill-content {
            padding: 20px 24px 24px !important;
            background: #fafafa !important;
        }
        
        .cursor-section {
            background: #ffffff !important;
            border-radius: 16px !important;
            padding: 20px !important;
            margin-bottom: 16px !important;
            border: 1px solid #e8e8e8 !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }
        
        .cursor-section:hover {
            border-color: #d0d0d0 !important;
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.06) !important;
            transform: translateY(-2px) !important;
        }
        
        .cursor-section-title {
            color: #000000 !important;
            font-size: 15px !important;
            font-weight: 600 !important;
            margin-bottom: 16px !important;
            letter-spacing: -0.3px !important;
            padding-bottom: 12px !important;
            border-bottom: 1px solid #f5f5f5 !important;
        }
        
        .cursor-config-row {
            display: flex !important;
            justify-content: space-between !important;
            align-items: center !important;
            margin-bottom: 12px !important;
        }
        
        .cursor-config-row:last-child {
            margin-bottom: 0 !important;
        }
        
        .cursor-config-label {
            color: #333 !important;
            font-size: 14px !important;
            font-weight: 500 !important;
        }
        
        .cursor-toggle-switch {
            position: relative !important;
            display: inline-block !important;
            width: 50px !important;
            height: 28px !important;
        }
        
        .cursor-toggle-switch input {
            opacity: 0 !important;
            width: 0 !important;
            height: 0 !important;
            position: absolute !important;
            pointer-events: none !important;
        }
        
        .cursor-toggle-slider {
            position: absolute !important;
            cursor: pointer !important;
            top: 0 !important;
            left: 0 !important;
            right: 0 !important;
            bottom: 0 !important;
            background-color: #e0e0e0 !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            border-radius: 28px !important;
        }
        
        .cursor-toggle-dot {
            position: absolute !important;
            height: 22px !important;
            width: 22px !important;
            left: 3px !important;
            bottom: 3px !important;
            background-color: white !important;
            border-radius: 50% !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
        }
        
        #cursor-bin-input {
            width: 100% !important;
            padding: 14px 16px !important;
            border: 1.5px solid #e0e0e0 !important;
            border-radius: 12px !important;
            font-size: 14px !important;
            font-family: 'SF Mono', Monaco, Consolas, monospace !important;
            background: #ffffff !important;
            color: #000000 !important;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }
        
        #cursor-bin-input:focus {
            outline: none !important;
            border-color: #000000 !important;
            box-shadow: 0 0 0 4px rgba(0, 0, 0, 0.05) !important;
        }
        
        .cursor-button-group {
            display: flex !important;
            gap: 12px !important;
            margin-top: 20px !important;
        }
        
        .cursor-btn {
            flex: 1 !important;
            padding: 14px 20px !important;
            border: none !important;
            border-radius: 12px !important;
            font-size: 15px !important;
            font-weight: 600 !important;
            cursor: pointer !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            letter-spacing: -0.2px !important;
        }
        
        .cursor-btn-start {
            background: #000000 !important;
            color: white !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
            border: none !important;
        }
        
        .cursor-btn-start:hover {
            background: #1a1a1a !important;
            transform: translateY(-3px) !important;
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.25) !important;
        }
        
        .cursor-btn-start:active {
            transform: translateY(-1px) !important;
        }
        
        .cursor-btn-running {
            background: #007AFF !important;
            color: white !important;
            box-shadow: 0 4px 12px rgba(0, 122, 255, 0.3) !important;
            border: none !important;
        }
        
        .cursor-btn-running:hover {
            background: #0066CC !important;
            transform: scale(1.02) !important;
            box-shadow: 0 6px 16px rgba(0, 122, 255, 0.4) !important;
        }
        
        .cursor-btn-stop {
            background: #ffffff !important;
            color: #ff3b30 !important;
            border: 2px solid #ff3b30 !important;
            box-shadow: 0 2px 8px rgba(255, 59, 48, 0.15) !important;
        }
        
        .cursor-btn-stop:hover {
            background: #fff5f5 !important;
            transform: translateY(-3px) !important;
            box-shadow: 0 6px 16px rgba(255, 59, 48, 0.3) !important;
        }
        
        .cursor-btn-stop:active {
            transform: translateY(-1px) !important;
        }
        
        .cursor-btn-icon {
            display: inline-block !important;
            margin-right: 6px !important;
        }
        
        .cursor-btn-icon.spinning {
            animation: cursor-spin 1s linear infinite !important;
        }
        
        #cursor-log-container {
            background: #ffffff !important;
            border-radius: 16px !important;
            padding: 20px !important;
            max-height: 260px !important;
            overflow-y: auto !important;
            border: 1px solid #e8e8e8 !important;
        }
        
        #cursor-log-title {
            color: #000000 !important;
            font-size: 15px !important;
            font-weight: 600 !important;
            margin-bottom: 16px !important;
            letter-spacing: -0.3px !important;
            padding-bottom: 12px !important;
            border-bottom: 1px solid #f5f5f5 !important;
        }
        
        #cursor-auto-fill-logs {
            font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace !important;
            font-size: 12px !important;
            line-height: 2 !important;
        }
        
        #cursor-auto-fill-logs::-webkit-scrollbar {
            width: 6px !important;
        }
        
        #cursor-auto-fill-logs::-webkit-scrollbar-track {
            background: transparent !important;
        }
        
        #cursor-auto-fill-logs::-webkit-scrollbar-thumb {
            background: #d8d8d8 !important;
            border-radius: 10px !important;
            transition: background 0.2s !important;
        }
        
        #cursor-auto-fill-logs::-webkit-scrollbar-thumb:hover {
            background: #b8b8b8 !important;
        }
        
        .cursor-log-item {
            margin: 8px 0 !important;
            padding: 0 !important;
            animation: cursor-fade-in 0.3s ease !important;
        }
        
        .cursor-log-timestamp {
            color: #999 !important;
            font-weight: 500 !important;
            margin-right: 8px !important;
        }
        
        .cursor-log-info .cursor-log-text {
            color: #007AFF !important;
        }
        
        .cursor-log-success .cursor-log-text {
            color: #34C759 !important;
            font-weight: 600 !important;
        }
        
        .cursor-log-error .cursor-log-text {
            color: #FF3B30 !important;
            font-weight: 600 !important;
        }
        
        .cursor-log-warning .cursor-log-text {
            color: #FF9500 !important;
            font-weight: 600 !important;
        }
        
        .cursor-status-badge {
            display: inline-block !important;
            padding: 6px 12px !important;
            border-radius: 8px !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            margin-top: 12px !important;
            letter-spacing: -0.2px !important;
        }
        
        .cursor-status-idle {
            background: #f5f5f5 !important;
            color: #666 !important;
        }
        
        .cursor-status-running {
            background: #e3f2fd !important;
            color: #007AFF !important;
            animation: cursor-pulse 2s ease-in-out infinite !important;
        }
        
        .cursor-status-stopped {
            background: #ffebee !important;
            color: #ff3b30 !important;
        }
    `;
    document.head.appendChild(style);

    // ===== 配置管理 =====
    const CONFIG_KEY = 'cursor_auto_fill_config';
    const QUEUE_KEY = 'cursor_url_queue';
    const defaultConfig = {
        autoFill: true,
        autoSubmit: true,
        bin: '379240xxxxxxxxx',
        batchMode: false,
        maxConcurrent: 1  // 单页面模式
    };

    function getConfig() {
        const saved = GM_getValue(CONFIG_KEY);
        return saved ? JSON.parse(saved) : defaultConfig;
    }

    function saveConfig(config) {
        GM_setValue(CONFIG_KEY, JSON.stringify(config));
    }

    let config = getConfig();

    // ===== URL队列管理 =====
    class URLQueue {
        constructor() {
            this.queue = this.load();
        }

        load() {
            const saved = GM_getValue(QUEUE_KEY);
            return saved ? JSON.parse(saved) : { urls: [], current: 0, status: 'idle' };
        }

        save() {
            GM_setValue(QUEUE_KEY, JSON.stringify(this.queue));
        }

        addURLs(urlText) {
            const urls = urlText.split('\n')
                .map(url => url.trim())
                .filter(url => url && url.startsWith('http'));
            
            this.queue = {
                urls: urls.map(url => ({ url, status: 'pending', timestamp: Date.now() })),
                current: 0,
                status: 'idle'
            };
            this.save();
            logger.log(`已添加 ${urls.length} 个URL到队列`, 'success');
            return urls.length;
        }

        getNext(count = 5) {
            const pending = this.queue.urls.filter(item => item.status === 'pending');
            const next = pending.slice(0, count);
            next.forEach(item => item.status = 'processing');
            this.save();
            return next.map(item => item.url);
        }

        markCompleted(url) {
            const item = this.queue.urls.find(item => item.url === url);
            if (item) {
                item.status = 'completed';
                this.queue.current++;
                this.save();
            }
        }

        getStats() {
            const total = this.queue.urls.length;
            const completed = this.queue.urls.filter(item => item.status === 'completed').length;
            const processing = this.queue.urls.filter(item => item.status === 'processing').length;
            const pending = this.queue.urls.filter(item => item.status === 'pending').length;
            return { total, completed, processing, pending };
        }

        clear() {
            this.queue = { urls: [], current: 0, status: 'idle' };
            this.save();
        }

        isComplete() {
            return this.queue.urls.length > 0 && 
                   this.queue.urls.every(item => item.status === 'completed');
        }
    }

    const urlQueue = new URLQueue();

    // ===== 日志系统 =====
    class Logger {
        constructor() {
            this.logs = [];
            this.maxLogs = 100;
        }

        log(message, type = 'info') {
            const timestamp = new Date().toLocaleTimeString();
            const logEntry = { timestamp, message, type };
            this.logs.push(logEntry);
            if (this.logs.length > this.maxLogs) {
                this.logs.shift();
            }
            console.log(`[Cursor Auto Fill] ${timestamp} [${type.toUpperCase()}] ${message}`);
            this.updateLogDisplay();
            this.autoScroll();
        }

        updateLogDisplay() {
            const logContainer = document.getElementById('cursor-auto-fill-logs');
            if (logContainer) {
                logContainer.innerHTML = this.logs.map(log => 
                    `<div class="cursor-log-item cursor-log-${log.type}">
                        <span class="cursor-log-timestamp">${log.timestamp}</span>
                        <span class="cursor-log-text">${log.message}</span>
                    </div>`
                ).join('');
            }
        }

        autoScroll() {
            const logContainer = document.getElementById('cursor-log-container');
            if (logContainer) {
                // 丝滑滚动到底部
                logContainer.scrollTo({
                    top: logContainer.scrollHeight,
                    behavior: 'smooth'
                });
            }
        }
    }

    const logger = new Logger();

    // ===== 更新UI状态 =====
    function updateUIState(state) {
        const actionBtn = document.getElementById('cursor-action-btn');
        const btnIcon = document.getElementById('cursor-btn-icon');
        const btnText = document.getElementById('cursor-btn-text');
        const statusBadge = document.getElementById('cursor-status-badge');

        if (state === 'running') {
            // 执行中状态
            if (actionBtn) {
                actionBtn.className = 'cursor-btn cursor-btn-running';
            }
            if (btnIcon) {
                btnIcon.className = 'cursor-btn-icon spinning';
                btnIcon.textContent = '⏸';
            }
            if (btnText) btnText.textContent = '执行中...';
            if (statusBadge) {
                statusBadge.className = 'cursor-status-badge cursor-status-running';
                statusBadge.textContent = '● 执行中';
                statusBadge.style.setProperty('background', '#e3f2fd', 'important');
                statusBadge.style.setProperty('color', '#007AFF', 'important');
            }
        } else if (state === 'stopped') {
            // 已停止状态
            if (actionBtn) {
                actionBtn.className = 'cursor-btn cursor-btn-stop';
            }
            if (btnIcon) {
                btnIcon.className = 'cursor-btn-icon';
                btnIcon.textContent = '■';
            }
            if (btnText) btnText.textContent = '已停止';
            if (statusBadge) {
                statusBadge.className = 'cursor-status-badge cursor-status-stopped';
                statusBadge.textContent = '● 已停止';
                statusBadge.style.setProperty('background', '#ffebee', 'important');
                statusBadge.style.setProperty('color', '#ff3b30', 'important');
            }
        } else {
            // 待机状态
            if (actionBtn) {
                actionBtn.className = 'cursor-btn cursor-btn-start';
            }
            if (btnIcon) {
                btnIcon.className = 'cursor-btn-icon';
                btnIcon.textContent = '▶';
            }
            if (btnText) btnText.textContent = '开始填写';
            if (statusBadge) {
                statusBadge.className = 'cursor-status-badge cursor-status-idle';
                statusBadge.textContent = '○ 待机中';
                statusBadge.style.setProperty('background', '#f5f5f5', 'important');
                statusBadge.style.setProperty('color', '#666', 'important');
            }
        }
    }

    // ===== Luhn算法生成卡号 =====
    function generateCardNumber(bin) {
        logger.log('开始生成卡号...', 'info');
        
        let cardNumber = '';
        for (let char of bin) {
            if (char.toLowerCase() === 'x') {
                cardNumber += Math.floor(Math.random() * 10);
            } else {
                cardNumber += char;
            }
        }

        cardNumber = cardNumber.slice(0, -1);

        let sum = 0;
        let shouldDouble = true;

        for (let i = cardNumber.length - 1; i >= 0; i--) {
            let digit = parseInt(cardNumber[i]);

            if (shouldDouble) {
                digit *= 2;
                if (digit > 9) {
                    digit -= 9;
                }
            }

            sum += digit;
            shouldDouble = !shouldDouble;
        }

        const checkDigit = (10 - (sum % 10)) % 10;
        cardNumber += checkDigit;

        logger.log(`卡号生成成功: ${cardNumber.replace(/(\d{4})/g, '$1 ').trim()}`, 'success');
        return cardNumber;
    }

    // ===== 生成随机卡片信息 =====
    function generateCardInfo() {
        // 每次都随机生成379240开头的卡号
        const cardNumber = generateCardNumber(config.bin);
        
        const now = new Date();
        const month = String(Math.floor(Math.random() * 12) + 1).padStart(2, '0');
        const year = String(now.getFullYear() + Math.floor(Math.random() * 2) + 1).slice(-2);
        
        // AmEx卡（34/37开头）CVV是4位，其他卡是3位
        const cardPrefix = cardNumber.substring(0, 2);
        const isAmex = cardPrefix === '34' || cardPrefix === '37';
        
        logger.log(`🔍 卡号前缀: ${cardPrefix}, 是否AmEx: ${isAmex}`, 'info');
        
        const cvv = isAmex 
            ? String(Math.floor(Math.random() * 9000) + 1000)  // 4位：1000-9999
            : String(Math.floor(Math.random() * 900) + 100);    // 3位：100-999

        logger.log(`✅ 生成到期日: ${month}/${year}, CVV: ${cvv} (${isAmex ? 'AmEx-4位' : '普通-3位'})`, 'success');

        return { cardNumber, month, year, cvv };
    }

    // ===== 生成随机美国地址 =====
    function generateUSAddress() {
        logger.log('生成随机美国地址...', 'info');

        const firstNames = ['James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph', 'Thomas', 'Charles'];
        const lastNames = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez'];
        
        const streets = ['Main St', 'Oak Ave', 'Pine St', 'Maple Ave', 'Cedar St', 'Elm St', 'Washington St', 'Lake St', 'Hill St', 'Park Ave'];
        const cities = [
            { name: 'New York', state: 'New York', zip: '10001' },
            { name: 'Los Angeles', state: 'California', zip: '90001' },
            { name: 'Chicago', state: 'Illinois', zip: '60601' },
            { name: 'Houston', state: 'Texas', zip: '77001' },
            { name: 'Phoenix', state: 'Arizona', zip: '85001' },
            { name: 'Philadelphia', state: 'Pennsylvania', zip: '19101' },
            { name: 'San Antonio', state: 'Texas', zip: '78201' },
            { name: 'San Diego', state: 'California', zip: '92101' },
            { name: 'Dallas', state: 'Texas', zip: '75201' },
            { name: 'San Jose', state: 'California', zip: '95101' }
        ];

        const firstName = firstNames[Math.floor(Math.random() * firstNames.length)];
        const lastName = lastNames[Math.floor(Math.random() * lastNames.length)];
        const fullName = `${firstName} ${lastName}`;

        const streetNumber = Math.floor(Math.random() * 9000) + 1000;
        const street = streets[Math.floor(Math.random() * streets.length)];
        const address1 = `${streetNumber} ${street}`;

        const cityInfo = cities[Math.floor(Math.random() * cities.length)];

        logger.log(`地址生成成功: ${fullName}, ${address1}, ${cityInfo.name}, ${cityInfo.state}`, 'success');

        return {
            name: fullName,
            address1: address1,
            city: cityInfo.name,
            state: cityInfo.state,
            zip: cityInfo.zip
        };
    }

    // ===== 等待元素出现 =====
    function waitForElement(selector, timeout = 10000) {
        return new Promise((resolve, reject) => {
            if (shouldStop) {
                reject(new Error('用户停止执行'));
                return;
            }

            const element = document.querySelector(selector);
            if (element) {
                return resolve(element);
            }

            const observer = new MutationObserver(() => {
                if (shouldStop) {
                    observer.disconnect();
                    reject(new Error('用户停止执行'));
                    return;
                }

                const element = document.querySelector(selector);
                if (element) {
                    observer.disconnect();
                    resolve(element);
                }
            });

            observer.observe(document.body, {
                childList: true,
                subtree: true
            });

            setTimeout(() => {
                observer.disconnect();
                reject(new Error(`等待元素超时: ${selector}`));
            }, timeout);
        });
    }

    // ===== 等待一段时间 =====
    function sleep(ms) {
        return new Promise(resolve => {
            if (shouldStop) {
                resolve();
                return;
            }
            setTimeout(resolve, ms);
        });
    }

    // ===== 填充输入框（使用setter触发React）=====
    async function fillInput(selector, value, label) {
        if (shouldStop) {
            throw new Error('用户停止执行');
        }

        try {
            logger.log(`填写${label}...`, 'info');
            const input = await waitForElement(selector, 8000);
            
            // 后台模式下减少延迟
            const isBackground = document.hidden;
            const delay = isBackground ? 5 : 15; // 后台模式下加快速度
            
            input.focus();
            await sleep(isBackground ? 30 : 100);
            
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 
                'value'
            ).set;
            
            nativeInputValueSetter.call(input, '');
            input.dispatchEvent(new Event('input', { bubbles: true }));
            await sleep(isBackground ? 20 : 50);
            
            for (let i = 0; i < value.length; i++) {
                if (shouldStop) throw new Error('用户停止执行');

                const currentValue = value.substring(0, i + 1);
                nativeInputValueSetter.call(input, currentValue);
                
                input.dispatchEvent(new KeyboardEvent('keydown', { 
                    bubbles: true, 
                    cancelable: true,
                    key: value[i],
                    code: `Key${value[i].toUpperCase()}`
                }));
                
                input.dispatchEvent(new Event('input', { 
                    bubbles: true, 
                    cancelable: true 
                }));
                
                input.dispatchEvent(new KeyboardEvent('keyup', { 
                    bubbles: true,
                    key: value[i],
                    code: `Key${value[i].toUpperCase()}`
                }));
                
                await sleep(delay);
            }
            
            await sleep(isBackground ? 50 : 100);
            input.dispatchEvent(new Event('change', { bubbles: true }));
            await sleep(isBackground ? 50 : 100);
            
            if (input.value !== value) {
                nativeInputValueSetter.call(input, value);
                input.dispatchEvent(new Event('input', { bubbles: true }));
                await sleep(isBackground ? 50 : 100);
            }
            
            input.blur();
            await sleep(isBackground ? 200 : 400);
            
            const actualValue = input.value;
            const normalizedActual = actualValue.replace(/[\s\/\-]/g, '');
            const normalizedExpected = value.replace(/[\s\/\-]/g, '');
            
            if (normalizedActual === normalizedExpected || actualValue === value) {
                logger.log(`✓ ${label}填写完成: ${actualValue}`, 'success');
            } else {
                logger.log(`⚠ ${label}值不匹配 (期望:${value}, 实际:${actualValue})`, 'warning');
            }
            
            return true;
        } catch (error) {
            if (error.message === '用户停止执行') {
                throw error;
            }
            logger.log(`❌ 填写${label}失败: ${error.message}`, 'error');
            return false;
        }
    }

    // ===== 填写表单 =====
    async function fillForm() {
        // 防止重复执行
        if (isRunning) {
            logger.log('⚠ 正在执行中，请勿重复点击', 'warning');
            return;
        }

        isRunning = true;
        shouldStop = false;
        updateUIState('running');

        try {
            logger.log('========== 开始自动填写 ==========', 'info');

            await sleep(500);

            // 1. 检查并展开银行卡区域
            logger.log('检查银行卡区域状态...', 'info');
            
            const cardRadio = document.querySelector('input[type="radio"][value="card"]');
            const isAlreadyExpanded = cardRadio && cardRadio.checked;
            
            if (isAlreadyExpanded) {
                logger.log('✓ 银行卡区域已展开', 'success');
                await sleep(200);
            } else {
                logger.log('点击展开银行卡区域...', 'info');
                const cardButton = document.querySelector('[data-testid="card-accordion-item-button"]');
                
                if (cardButton) {
                    cardButton.click();
                    await sleep(800);
                    
                    const radioAfterClick = document.querySelector('input[type="radio"][value="card"]');
                    if (radioAfterClick && radioAfterClick.checked) {
                        logger.log('✓ 银行卡区域已展开', 'success');
                    } else {
                        throw new Error('银行卡区域展开失败');
                    }
                } else {
                    throw new Error('未找到银行卡展开按钮');
                }
            }
            
            if (shouldStop) throw new Error('用户停止执行');

            // 等待输入框渲染
            logger.log('等待输入框渲染...', 'info');
            await waitForElement('input[name="number"], input[placeholder*="卡号"], input[autocomplete="cc-number"]', 5000);
            logger.log('✓ 输入框已就绪', 'success');

            // 生成信息
            const cardInfo = generateCardInfo();
            const address = generateUSAddress();

            // 2. 填写卡号
            await fillInput(
                'input[name="number"], input[placeholder*="卡号"], input[autocomplete="cc-number"]',
                cardInfo.cardNumber, 
                '卡号'
            );

            // 3. 填写到期日
            await fillInput(
                'input[name="expiry"], input[placeholder*="到期"], input[autocomplete="cc-exp"]',
                `${cardInfo.month}${cardInfo.year}`, 
                '到期日'
            );

            // 4. 填写CVV
            await fillInput(
                'input[name="cvc"], input[placeholder*="CVC"], input[placeholder*="安全码"], input[autocomplete="cc-csc"]',
                cardInfo.cvv, 
                'CVV'
            );

            // 5. 填写持卡人姓名
            await fillInput(
                'input[name="name"], input[placeholder*="姓名"], input[autocomplete="cc-name"]',
                address.name, 
                '持卡人姓名'
            );

            if (shouldStop) throw new Error('用户停止执行');

            // 6. 点击"手动输入地址"按钮（如果存在）
            logger.log('查找"手动输入地址"按钮...', 'info');
            const manualAddressButton = Array.from(document.querySelectorAll('button')).find(btn => 
                btn.textContent.includes('手动输入地址') || 
                btn.textContent.includes('Enter address manually')
            );
            
            if (manualAddressButton) {
                logger.log('点击"手动输入地址"...', 'info');
                manualAddressButton.click();
                await sleep(500);
                logger.log('✓ 已展开手动输入', 'success');
            }

            // 7. 选择国家 - 美国
            logger.log('选择国家：美国...', 'info');
            const allSelects = document.querySelectorAll('select');
            const countrySelect = document.querySelector('select[name="billingCountry"]') || allSelects[0];
            
            if (countrySelect) {
                logger.log(`当前国家: ${countrySelect.value}`, 'info');
                
                let usOption = null;
                for (let option of countrySelect.options) {
                    if (option.value === 'US' || option.textContent.trim() === '美国') {
                        usOption = option;
                        break;
                    }
                }
                
                if (usOption) {
                    countrySelect.value = usOption.value;
                    countrySelect.dispatchEvent(new Event('input', { bubbles: true }));
                    countrySelect.dispatchEvent(new Event('change', { bubbles: true }));
                    await sleep(1500);
                    logger.log('✓ 已选择美国', 'success');
                }
            }

            if (shouldStop) throw new Error('用户停止执行');

            // 8. 填写地址
            await fillInput(
                'input[name="line1"], input[placeholder*="地址"]',
                address.address1, 
                '地址'
            );

            // 9. 填写城市
            await fillInput(
                'input[name="city"], input[placeholder*="城市"]',
                address.city, 
                '城市'
            );

            // 10. 填写邮编
            await fillInput(
                'input[name="zip"], input[placeholder*="邮编"]',
                address.zip, 
                '邮编'
            );

            await sleep(800);

            // 11. 检查州
            const allSelectsAfter = document.querySelectorAll('select');
            const stateSelect = allSelectsAfter.length > 1 ? allSelectsAfter[1] : null;
            
            if (stateSelect && stateSelect.value) {
                logger.log(`✓ 州已自动选择: ${stateSelect.value}`, 'success');
            }

            logger.log('========== 所有字段填写完成 ==========', 'success');

            if (shouldStop) throw new Error('用户停止执行');

            // 检查并提交，等待跳转完成
            const submitted = await checkAndSubmit();
            return submitted;

        } catch (error) {
            if (error.message === '用户停止执行') {
                logger.log('========== 执行已停止 ==========', 'warning');
                updateUIState('stopped');
            } else {
                logger.log(`❌ 错误: ${error.message}`, 'error');
                updateUIState('idle');
            }
            return false;
        } finally {
            isRunning = false;
        }
    }

    // ===== 此函数已废弃，不再使用 =====
    // function waitForNavigation() - 已移除，点击提交后直接2秒关闭

    // ===== 检查并提交 =====
    async function checkAndSubmit() {
        try {
            logger.log('检查提交按钮状态...', 'info');
            
            const submitButton = document.querySelector('button[type="submit"]');
            if (!submitButton) {
                logger.log('未找到提交按钮', 'warning');
                updateUIState('idle');
                return false;
            }

            const checkButtonReady = () => {
                const isBasicReady = !submitButton.disabled && 
                                    !submitButton.hasAttribute('disabled') &&
                                    submitButton.offsetParent !== null;
                
                const processingText = submitButton.querySelector('[class*="processing"]');
                const isProcessing = processingText && processingText.offsetParent !== null;
                
                const classList = submitButton.className;
                const hasDisabledClass = classList.includes('disabled') || classList.includes('Disabled');
                
                return isBasicReady && !isProcessing && !hasDisabledClass;
            };

            logger.log('快速检测按钮状态（最多5秒）...', 'info');
            
            // 等待按钮就绪 - 优化：每次只等0.2秒
            let attempts = 0;
            const maxAttempts = 25; // 25次 × 0.2秒 = 5秒
            
            while (attempts < maxAttempts && !checkButtonReady()) {
                if (shouldStop) {
                    updateUIState('stopped');
                    return false;
                }
                await sleep(200); // 每0.2秒检测一次，提速5倍
                attempts++;
            }
            
            if (!checkButtonReady()) {
                logger.log('⚠ 按钮未就绪，但继续尝试提交', 'warning');
            } else {
                logger.log(`✓ 提交按钮已就绪！(用时 ${(attempts * 0.2).toFixed(1)}秒)`, 'success');
            }
            
            if (config.autoSubmit) {
                logger.log('立即提交...', 'info');
                
                if (!shouldStop) {
                    submitButton.click();
                    logger.log('✓ 已点击提交按钮！', 'success');
                    
                    // 等待3秒检测支付结果
                    await sleep(3000);
                    
                    // 检测是否支付失败
                    if (isPaymentFailed()) {
                        logger.log('❌❌❌ 支付失败，需要重试！', 'error');
                        updateUIState('idle');
                        return false; // 返回false表示失败，需要重试
                    }
                    
                    logger.log('✅ 提交完成！', 'success');
                    updateUIState('idle');
                    
                    // 标记当前URL完成并跳转到下一个
                    await jumpToNextURL();
                    
                    return true;
                }
            } else {
                logger.log('自动提交未启用，请手动点击"开始试用"', 'info');
                updateUIState('idle');
                return false;
            }

        } catch (error) {
            logger.log(`检查提交按钮时出错: ${error.message}`, 'error');
            updateUIState('idle');
            return false;
        }
    }

    // ===== 停止执行 =====
    function stopExecution() {
        shouldStop = true;
        logger.log('正在停止执行...', 'warning');
        updateUIState('stopped');
        
        setTimeout(() => {
            shouldStop = false;
            updateUIState('idle');
        }, 2000);
    }

    // ===== 检测支付是否失败 =====
    function isPaymentFailed() {
        const pageText = document.body.textContent || document.body.innerText || '';
        const pageHTML = document.body.innerHTML || '';
        
        // 检测"支付失败"相关文本
        const failedIndicators = [
            '您的卡被拒绝',
            '卡被拒绝',
            '支付失败',
            '付款失败',
            'card was declined',
            'payment failed',
            'card declined',
            'declined',
            'was declined',
            '交易失败',
            '无法处理',
            'cannot process',
            'unable to process'
        ];
        
        for (const indicator of failedIndicators) {
            if (pageText.includes(indicator) || pageHTML.includes(indicator)) {
                logger.log(`❌ 检测到支付失败: "${indicator}"`, 'error');
                return true;
            }
        }
        
        return false;
    }

    // ===== 检测页面是否已完成支付 =====
    function isAlreadyCompleted() {
        const pageText = document.body.textContent || document.body.innerText || '';
        const pageHTML = document.body.innerHTML || '';
        
        logger.log('检测页面是否已被使用...', 'info');
        
        // 检测"已完成"相关文本（中英文）
        const completedIndicators = [
            '您已全部完成',
            '您已经完成付款',
            '本结账会话已超时',
            '结账会话已超时',
            'already completed',
            'payment completed',
            'session expired',
            'checkout session has expired',
            'session has expired',
            '会话已超时',
            '已超时'
        ];
        
        for (const indicator of completedIndicators) {
            if (pageText.includes(indicator) || pageHTML.includes(indicator)) {
                logger.log(`✓✓✓ 检测到已使用标志: "${indicator}"`, 'success');
                return true;
            }
        }
        
        // 检查是否没有输入框（说明不是正常的支付页面）
        const hasInputs = document.querySelectorAll('input[type="text"], input[autocomplete]').length > 0;
        const hasSubmitButton = document.querySelector('button[type="submit"]') !== null;
        
        if (!hasInputs && !hasSubmitButton) {
            logger.log('✓ 页面没有输入框和提交按钮，可能已使用', 'info');
            return true;
        }
        
        logger.log('页面正常，未检测到已使用标志', 'info');
        return false;
    }

    // ===== 检测Cursor试用页面 =====
    function isCursorTrialPage() {
        if (!window.location.href.includes('checkout.stripe.com')) {
            return false;
        }

        const title = document.title;
        if (title.includes('Cursor')) {
            logger.log('✓ 检测到 Cursor 试用页面', 'success');
            return true;
        }

        const pageText = document.body.textContent;
        if (pageText.includes('Cursor Ultra') || pageText.includes('试用 Cursor')) {
            logger.log('✓ 检测到 Cursor 试用页面', 'success');
            return true;
        }
        
        return false;
    }

    // ===== 等待页面加载 =====
    function waitForPageLoad() {
        return new Promise((resolve) => {
            let attempts = 0;
            const maxAttempts = 10; // 改为5秒超时
            
            const checkInterval = setInterval(() => {
                attempts++;
                
                if (isCursorTrialPage()) {
                    clearInterval(checkInterval);
                    logger.log(`✓ 检测到Cursor页面 (用时${attempts}秒)`, 'success');
                    resolve(true);
                    return;
                }
                
                if (attempts >= maxAttempts) {
                    clearInterval(checkInterval);
                    logger.log('✓ 页面检测完成，继续执行', 'info');
                    resolve(true); // 改为总是返回true，不阻塞
                }
            }, 1000); // 每秒检测一次
        });
    }

    // ===== 创建UI界面 =====
    function createUI() {
        const oldUI = document.getElementById('cursor-auto-fill-container');
        if (oldUI) {
            oldUI.remove();
        }

        const container = document.createElement('div');
        container.id = 'cursor-auto-fill-container';
        
        container.innerHTML = `
            <div id="cursor-auto-fill-panel">
                <div id="cursor-auto-fill-header">
                    <div id="cursor-auto-fill-header-row">
                        <div id="cursor-auto-fill-header-title">Cursor 自动填写</div>
                        <button id="cursor-auto-fill-toggle">−</button>
                    </div>
                    <div id="cursor-status-badge" class="cursor-status-badge cursor-status-idle">○ 待机中</div>
                </div>
                <div id="cursor-auto-fill-content">
                    <div class="cursor-section">
                        <div class="cursor-section-title">功能设置</div>
                        <div class="cursor-config-row">
                            <label class="cursor-config-label">自动填写</label>
                            <label class="cursor-toggle-switch">
                                <input type="checkbox" id="cursor-auto-fill-toggle-input" ${config.autoFill ? 'checked' : ''}>
                                <span class="cursor-toggle-slider">
                                    <span class="cursor-toggle-dot"></span>
                                </span>
                            </label>
                        </div>
                        <div class="cursor-config-row">
                            <label class="cursor-config-label">自动提交</label>
                            <label class="cursor-toggle-switch">
                                <input type="checkbox" id="cursor-auto-submit-toggle" ${config.autoSubmit ? 'checked' : ''}>
                                <span class="cursor-toggle-slider">
                                    <span class="cursor-toggle-dot"></span>
                                </span>
                            </label>
                        </div>
                    </div>
                    
                    <div class="cursor-section">
                        <div class="cursor-section-title">BIN 配置</div>
                        <input type="text" id="cursor-bin-input" value="${config.bin}" placeholder="379240xxxxxxxxx">
                    </div>
                    
                    <div class="cursor-section">
                        <div class="cursor-section-title">批量处理</div>
                        <div style="margin-bottom: 12px;">
                            <label style="color: #666; font-size: 13px; display: block; margin-bottom: 6px;">批量URL（每行一个）</label>
                            <textarea id="cursor-url-batch" placeholder="https://checkout.stripe.com/c/pay/...
https://checkout.stripe.com/c/pay/...
https://checkout.stripe.com/c/pay/..." style="width: 100%; height: 120px; padding: 10px; border: 1.5px solid #e0e0e0; border-radius: 8px; font-family: monospace; font-size: 12px; resize: vertical;"></textarea>
                        </div>
                        <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 12px;">
                            <button id="cursor-batch-start" style="flex: 1; padding: 10px; background: #000; color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer;">开始批量处理</button>
                            <button id="cursor-batch-clear" style="padding: 10px 16px; background: #f5f5f5; color: #666; border: none; border-radius: 8px; font-weight: 600; cursor: pointer;">清空队列</button>
                        </div>
                        <div id="cursor-batch-stats" style="font-size: 12px; color: #666; padding: 8px; background: #f9f9f9; border-radius: 6px; display: none;">
                            <div>总数: <span id="stat-total">0</span> | 完成: <span id="stat-completed">0</span> | 处理中: <span id="stat-processing">0</span> | 待处理: <span id="stat-pending">0</span></div>
                        </div>
                    </div>
                    
                    <div class="cursor-button-group">
                        <button id="cursor-action-btn" class="cursor-btn cursor-btn-start">
                            <span id="cursor-btn-icon">▶</span>
                            <span id="cursor-btn-text">开始填写</span>
                        </button>
                    </div>
                    
                    <div id="cursor-log-container" class="cursor-section">
                        <div id="cursor-log-title">执行日志</div>
                        <div id="cursor-auto-fill-logs"></div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(container);
        
        // JavaScript强制设置所有样式
        const panel = document.getElementById('cursor-auto-fill-panel');
        if (panel) {
            panel.style.setProperty('position', 'fixed', 'important');
            panel.style.setProperty('top', '24px', 'important');
            panel.style.setProperty('right', '24px', 'important');
            panel.style.setProperty('max-width', '420px', 'important');
            panel.style.setProperty('min-width', '360px', 'important');
            panel.style.setProperty('width', 'auto', 'important');
            panel.style.setProperty('background', '#ffffff', 'important');
            panel.style.setProperty('border-radius', '20px', 'important');
            panel.style.setProperty('box-shadow', '0 24px 48px rgba(0, 0, 0, 0.1), 0 0 0 1px rgba(0, 0, 0, 0.05)', 'important');
            panel.style.setProperty('z-index', '2147483647', 'important');
            panel.style.setProperty('overflow', 'visible', 'important');
            panel.style.setProperty('font-family', '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', 'important');
        }
        
        const header = document.getElementById('cursor-auto-fill-header');
        if (header) {
            header.style.setProperty('background', '#ffffff', 'important');
            header.style.setProperty('padding', '24px', 'important');
            header.style.setProperty('border-bottom', '1px solid #f0f0f0', 'important');
        }
        
        const headerRow = document.getElementById('cursor-auto-fill-header-row');
        if (headerRow) {
            headerRow.style.setProperty('display', 'flex', 'important');
            headerRow.style.setProperty('justify-content', 'space-between', 'important');
            headerRow.style.setProperty('align-items', 'center', 'important');
            headerRow.style.setProperty('margin-bottom', '12px', 'important');
        }
        
        const headerTitle = document.getElementById('cursor-auto-fill-header-title');
        if (headerTitle) {
            headerTitle.style.setProperty('font-size', '20px', 'important');
            headerTitle.style.setProperty('font-weight', '700', 'important');
            headerTitle.style.setProperty('color', '#000000', 'important');
            headerTitle.style.setProperty('letter-spacing', '-0.5px', 'important');
        }
        
        const toggleHeaderBtn = document.getElementById('cursor-auto-fill-toggle');
        if (toggleHeaderBtn) {
            toggleHeaderBtn.style.setProperty('background', '#f5f5f5', 'important');
            toggleHeaderBtn.style.setProperty('border', 'none', 'important');
            toggleHeaderBtn.style.setProperty('color', '#666', 'important');
            toggleHeaderBtn.style.setProperty('width', '36px', 'important');
            toggleHeaderBtn.style.setProperty('height', '36px', 'important');
            toggleHeaderBtn.style.setProperty('border-radius', '10px', 'important');
            toggleHeaderBtn.style.setProperty('cursor', 'pointer', 'important');
            toggleHeaderBtn.style.setProperty('font-size', '22px', 'important');
            toggleHeaderBtn.style.setProperty('line-height', '1', 'important');
        }
        
        const statusBadge = document.getElementById('cursor-status-badge');
        if (statusBadge) {
            statusBadge.style.setProperty('display', 'inline-block', 'important');
            statusBadge.style.setProperty('padding', '6px 12px', 'important');
            statusBadge.style.setProperty('border-radius', '8px', 'important');
            statusBadge.style.setProperty('font-size', '13px', 'important');
            statusBadge.style.setProperty('font-weight', '600', 'important');
        }
        
        const content = document.getElementById('cursor-auto-fill-content');
        if (content) {
            content.style.setProperty('padding', '20px 24px 24px', 'important');
            content.style.setProperty('background', '#fafafa', 'important');
        }
        
        const actionBtn = document.getElementById('cursor-action-btn');
        if (actionBtn) {
            actionBtn.style.setProperty('background', '#000000', 'important');
            actionBtn.style.setProperty('color', 'white', 'important');
            actionBtn.style.setProperty('border', 'none', 'important');
            actionBtn.style.setProperty('box-shadow', '0 4px 12px rgba(0, 0, 0, 0.15)', 'important');
        }
        
        const btnIcon = document.getElementById('cursor-btn-icon');
        if (btnIcon) {
            btnIcon.style.setProperty('display', 'inline-block', 'important');
            btnIcon.style.setProperty('margin-right', '6px', 'important');
        }
        
        const btnText = document.getElementById('cursor-btn-text');
        if (btnText) {
            btnText.style.setProperty('display', 'inline-block', 'important');
        }
        
        // 设置所有section样式
        const sections = document.querySelectorAll('.cursor-section');
        sections.forEach(section => {
            section.style.setProperty('background', '#ffffff', 'important');
            section.style.setProperty('border-radius', '16px', 'important');
            section.style.setProperty('padding', '20px', 'important');
            section.style.setProperty('margin-bottom', '16px', 'important');
            section.style.setProperty('border', '1px solid #e8e8e8', 'important');
        });
        
        // 设置section标题
        const sectionTitles = document.querySelectorAll('.cursor-section-title');
        sectionTitles.forEach(title => {
            title.style.setProperty('color', '#000000', 'important');
            title.style.setProperty('font-size', '15px', 'important');
            title.style.setProperty('font-weight', '600', 'important');
            title.style.setProperty('margin-bottom', '16px', 'important');
            title.style.setProperty('padding-bottom', '12px', 'important');
            title.style.setProperty('border-bottom', '1px solid #f5f5f5', 'important');
        });
        
        // 设置config rows
        const configRows = document.querySelectorAll('.cursor-config-row');
        configRows.forEach(row => {
            row.style.setProperty('display', 'flex', 'important');
            row.style.setProperty('justify-content', 'space-between', 'important');
            row.style.setProperty('align-items', 'center', 'important');
            row.style.setProperty('margin-bottom', '12px', 'important');
        });
        
        // 设置config labels
        const configLabels = document.querySelectorAll('.cursor-config-label');
        configLabels.forEach(label => {
            label.style.setProperty('color', '#333', 'important');
            label.style.setProperty('font-size', '14px', 'important');
            label.style.setProperty('font-weight', '500', 'important');
        });
        
        // 设置toggle switches
        const toggleSwitches = document.querySelectorAll('.cursor-toggle-switch');
        toggleSwitches.forEach(toggle => {
            toggle.style.setProperty('position', 'relative', 'important');
            toggle.style.setProperty('display', 'inline-block', 'important');
            toggle.style.setProperty('width', '50px', 'important');
            toggle.style.setProperty('height', '28px', 'important');
        });
        
        // 强制隐藏所有复选框input
        const toggleInputs = document.querySelectorAll('.cursor-toggle-switch input');
        toggleInputs.forEach(input => {
            input.style.setProperty('opacity', '0', 'important');
            input.style.setProperty('width', '0', 'important');
            input.style.setProperty('height', '0', 'important');
            input.style.setProperty('position', 'absolute', 'important');
            input.style.setProperty('pointer-events', 'none', 'important');
            input.style.setProperty('visibility', 'hidden', 'important');
            input.style.setProperty('display', 'none', 'important');
        });
        
        // 设置toggle sliders
        const toggleSliders = document.querySelectorAll('.cursor-toggle-slider');
        toggleSliders.forEach(slider => {
            slider.style.setProperty('position', 'absolute', 'important');
            slider.style.setProperty('cursor', 'pointer', 'important');
            slider.style.setProperty('top', '0', 'important');
            slider.style.setProperty('left', '0', 'important');
            slider.style.setProperty('right', '0', 'important');
            slider.style.setProperty('bottom', '0', 'important');
            slider.style.setProperty('background-color', '#e0e0e0', 'important');
            slider.style.setProperty('border-radius', '28px', 'important');
            slider.style.setProperty('transition', 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)', 'important');
        });
        
        // 设置toggle dots（开关圆点）
        const toggleDots = document.querySelectorAll('.cursor-toggle-dot');
        toggleDots.forEach(dot => {
            dot.style.setProperty('position', 'absolute', 'important');
            dot.style.setProperty('height', '22px', 'important');
            dot.style.setProperty('width', '22px', 'important');
            dot.style.setProperty('left', '3px', 'important');
            dot.style.setProperty('bottom', '3px', 'important');
            dot.style.setProperty('background-color', 'white', 'important');
            dot.style.setProperty('border-radius', '50%', 'important');
            dot.style.setProperty('transition', 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)', 'important');
            dot.style.setProperty('box-shadow', '0 2px 4px rgba(0, 0, 0, 0.1)', 'important');
        });
        
        // 处理开关选中状态
        const autoFillInput = document.getElementById('cursor-auto-fill-toggle-input');
        const autoSubmitInput = document.getElementById('cursor-auto-submit-toggle');
        
        function updateToggleState(input) {
            const slider = input.nextElementSibling;
            const dot = slider ? slider.querySelector('.cursor-toggle-dot') : null;
            
            if (input.checked) {
                if (slider) slider.style.setProperty('background-color', '#000000', 'important');
                if (dot) dot.style.setProperty('transform', 'translateX(22px)', 'important');
            } else {
                if (slider) slider.style.setProperty('background-color', '#e0e0e0', 'important');
                if (dot) dot.style.setProperty('transform', 'translateX(0)', 'important');
            }
        }
        
        if (autoFillInput) updateToggleState(autoFillInput);
        if (autoSubmitInput) updateToggleState(autoSubmitInput);
        
        // 设置BIN输入框
        const binInput = document.getElementById('cursor-bin-input');
        if (binInput) {
            binInput.style.setProperty('width', '100%', 'important');
            binInput.style.setProperty('padding', '14px 16px', 'important');
            binInput.style.setProperty('border', '1.5px solid #e0e0e0', 'important');
            binInput.style.setProperty('border-radius', '12px', 'important');
            binInput.style.setProperty('font-size', '14px', 'important');
            binInput.style.setProperty('background', '#ffffff', 'important');
            binInput.style.setProperty('color', '#000000', 'important');
            binInput.style.setProperty('font-family', '"SF Mono", Monaco, Consolas, monospace', 'important');
        }
        
        // 设置按钮组
        const btnGroup = document.querySelector('.cursor-button-group');
        if (btnGroup) {
            btnGroup.style.setProperty('margin-top', '20px', 'important');
            btnGroup.style.setProperty('margin-bottom', '20px', 'important');
        }
        
        // 设置所有按钮通用样式
        const allBtns = document.querySelectorAll('.cursor-btn');
        allBtns.forEach(btn => {
            btn.style.setProperty('width', '100%', 'important');
            btn.style.setProperty('padding', '14px 20px', 'important');
            btn.style.setProperty('border-radius', '12px', 'important');
            btn.style.setProperty('font-size', '15px', 'important');
            btn.style.setProperty('font-weight', '600', 'important');
            btn.style.setProperty('cursor', 'pointer', 'important');
            btn.style.setProperty('transition', 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)', 'important');
            btn.style.setProperty('letter-spacing', '-0.2px', 'important');
        });
        
        // 设置日志容器
        const logContainer = document.getElementById('cursor-log-container');
        if (logContainer) {
            logContainer.style.setProperty('background', '#ffffff', 'important');
            logContainer.style.setProperty('border-radius', '16px', 'important');
            logContainer.style.setProperty('padding', '20px', 'important');
            logContainer.style.setProperty('max-height', '260px', 'important');
            logContainer.style.setProperty('overflow-y', 'auto', 'important');
            logContainer.style.setProperty('border', '1px solid #e8e8e8', 'important');
        }
        
        // 设置日志标题
        const logTitle = document.getElementById('cursor-log-title');
        if (logTitle) {
            logTitle.style.setProperty('color', '#000000', 'important');
            logTitle.style.setProperty('font-size', '15px', 'important');
            logTitle.style.setProperty('font-weight', '600', 'important');
            logTitle.style.setProperty('margin-bottom', '16px', 'important');
            logTitle.style.setProperty('padding-bottom', '12px', 'important');
            logTitle.style.setProperty('border-bottom', '1px solid #f5f5f5', 'important');
        }
        
        // 设置日志区域
        const logs = document.getElementById('cursor-auto-fill-logs');
        if (logs) {
            logs.style.setProperty('font-family', '"SF Mono", Monaco, Consolas, monospace', 'important');
            logs.style.setProperty('font-size', '12px', 'important');
            logs.style.setProperty('line-height', '2', 'important');
        }
        
        // 定时检查并设置日志项颜色（因为日志是动态添加的）
        setInterval(() => {
            const logItems = document.querySelectorAll('.cursor-log-item');
            logItems.forEach(item => {
                const timestamp = item.querySelector('.cursor-log-timestamp');
                const text = item.querySelector('.cursor-log-text');
                
                if (timestamp) {
                    timestamp.style.setProperty('color', '#a0a0a0', 'important');
                    timestamp.style.setProperty('font-weight', '500', 'important');
                }
                
                if (text) {
                    if (item.classList.contains('cursor-log-success')) {
                        text.style.setProperty('color', '#34C759', 'important');
                        text.style.setProperty('font-weight', '600', 'important');
                    } else if (item.classList.contains('cursor-log-error')) {
                        text.style.setProperty('color', '#FF3B30', 'important');
                        text.style.setProperty('font-weight', '600', 'important');
                    } else if (item.classList.contains('cursor-log-warning')) {
                        text.style.setProperty('color', '#FF9500', 'important');
                        text.style.setProperty('font-weight', '600', 'important');
                    } else if (item.classList.contains('cursor-log-info')) {
                        text.style.setProperty('color', '#007AFF', 'important');
                    }
                }
            });
        }, 100); // 每100ms检查一次
        
        logger.log('✓ UI界面已创建', 'success');

        setupUIEvents();
        makeDraggable();
        logger.updateLogDisplay();
    }

    // ===== 设置UI事件 =====
    function setupUIEvents() {
        // 折叠按钮
        const toggleBtn = document.getElementById('cursor-auto-fill-toggle');
        const content = document.getElementById('cursor-auto-fill-content');
        let isCollapsed = false;

        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            isCollapsed = !isCollapsed;
            content.style.display = isCollapsed ? 'none' : 'block';
            toggleBtn.textContent = isCollapsed ? '+' : '−';
        });

        // 自动填写开关
        const autoFillInput = document.getElementById('cursor-auto-fill-toggle-input');
        autoFillInput.addEventListener('change', (e) => {
            config.autoFill = e.target.checked;
            saveConfig(config);
            logger.log(`自动填写已${config.autoFill ? '开启' : '关闭'}`, 'info');
            updateToggleVisual(e.target);
        });

        // 自动提交开关
        const autoSubmitInput = document.getElementById('cursor-auto-submit-toggle');
        autoSubmitInput.addEventListener('change', (e) => {
            config.autoSubmit = e.target.checked;
            saveConfig(config);
            logger.log(`自动提交已${config.autoSubmit ? '开启' : '关闭'}`, 'info');
            updateToggleVisual(e.target);
        });
        
        // 更新开关视觉状态的函数
        function updateToggleVisual(input) {
            const slider = input.nextElementSibling;
            const dot = slider ? slider.querySelector('.cursor-toggle-dot') : null;
            
            if (input.checked) {
                if (slider) slider.style.setProperty('background-color', '#000000', 'important');
                if (dot) dot.style.setProperty('transform', 'translateX(22px)', 'important');
            } else {
                if (slider) slider.style.setProperty('background-color', '#e0e0e0', 'important');
                if (dot) dot.style.setProperty('transform', 'translateX(0)', 'important');
            }
        }

        // BIN输入
        document.getElementById('cursor-bin-input').addEventListener('change', (e) => {
            config.bin = e.target.value;
            saveConfig(config);
            logger.log(`BIN已更新: ${config.bin}`, 'info');
        });
        
        // 批量处理按钮
        document.getElementById('cursor-batch-start').addEventListener('click', (e) => {
            e.stopPropagation();
            const urlText = document.getElementById('cursor-url-batch').value;
            if (!urlText.trim()) {
                logger.log('请输入URL列表', 'warning');
                return;
            }
            
            const count = urlQueue.addURLs(urlText);
            if (count > 0) {
                document.getElementById('cursor-batch-stats').style.display = 'block';
                updateBatchStats();
                startBatchProcessing();
            }
        });
        
        // 清空队列按钮
        document.getElementById('cursor-batch-clear').addEventListener('click', (e) => {
            e.stopPropagation();
            urlQueue.clear();
            document.getElementById('cursor-url-batch').value = '';
            document.getElementById('cursor-batch-stats').style.display = 'none';
            logger.log('队列已清空', 'info');
        });

        // 动作按钮（开始/停止切换）
        document.getElementById('cursor-action-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            
            if (isRunning) {
                // 当前正在执行，点击停止
                logger.log('========== 用户停止执行 ==========', 'warning');
                stopExecution();
            } else {
                // 当前待机，点击开始
                logger.log('========== 手动触发填写 ==========', 'info');
                fillForm();
            }
        });
    }

    // ===== 使面板可拖拽 =====
    function makeDraggable() {
        const panel = document.getElementById('cursor-auto-fill-panel');
        const header = document.getElementById('cursor-auto-fill-header');
        let isDragging = false;
        let currentX, currentY, initialX, initialY;

        header.addEventListener('mousedown', (e) => {
            if (e.target.id === 'cursor-auto-fill-toggle') return;
            isDragging = true;
            initialX = e.clientX - panel.offsetLeft;
            initialY = e.clientY - panel.offsetTop;
        });

        document.addEventListener('mousemove', (e) => {
            if (isDragging) {
                e.preventDefault();
                currentX = e.clientX - initialX;
                currentY = e.clientY - initialY;

                panel.style.left = currentX + 'px';
                panel.style.top = currentY + 'px';
                panel.style.right = 'auto';
            }
        });

        document.addEventListener('mouseup', () => {
            isDragging = false;
        });
    }

    // ===== 批量处理逻辑 =====
    let batchMonitorInterval = null; // 全局监控interval
    
    function updateBatchStats() {
        const stats = urlQueue.getStats();
        const totalEl = document.getElementById('stat-total');
        const completedEl = document.getElementById('stat-completed');
        const processingEl = document.getElementById('stat-processing');
        const pendingEl = document.getElementById('stat-pending');
        
        if (totalEl) totalEl.textContent = stats.total;
        if (completedEl) completedEl.textContent = stats.completed;
        if (processingEl) processingEl.textContent = stats.processing;
        if (pendingEl) pendingEl.textContent = stats.pending;
    }
    
    // 从文本框中删除已完成的所有URL
    function updateTextareaWithPendingURLs() {
        const textarea = document.getElementById('cursor-url-batch');
        if (!textarea) return;
        
        // 获取队列中所有completed的URL
        const completedURLs = urlQueue.queue.urls
            .filter(item => item.status === 'completed')
            .map(item => item.url);
        
        if (completedURLs.length === 0) return;
        
        const currentText = textarea.value;
        const lines = currentText.split('\n');
        
        // 过滤掉所有已完成的URL
        const completedIDs = completedURLs.map(url => {
            const match = url.match(/\/pay\/([^\/\?]+)/);
            return match ? match[1] : null;
        }).filter(id => id);
        
        const filteredLines = lines.filter(line => {
            const lineMatch = line.trim().match(/\/pay\/([^\/\?]+)/);
            if (lineMatch && completedIDs.includes(lineMatch[1])) {
                return false; // 过滤掉已完成的
            }
            // 如果不是URL格式的行（如空行），保留
            return line.trim().length === 0 || !line.includes('checkout.stripe.com');
        });
        
        const newText = filteredLines.join('\n').trim();
        if (newText !== currentText.trim()) {
            textarea.value = newText;
            logger.log(`✓ 已从列表中移除 ${completedURLs.length} 个完成的URL`, 'info');
        }
    }

    // ===== 单页面批量处理 =====
    function startBatchProcessing() {
        const stats = urlQueue.getStats();
        logger.log(`========== 单页面批量处理 v2.4.0 ==========`, 'success');
        logger.log(`共 ${stats.total} 个URL，当前页面逐个处理`, 'info');
        updateBatchStats();
        
        // 只获取1个URL，在当前标签页打开
        const nextURLs = urlQueue.getNext(1);
        if (nextURLs.length > 0) {
            const nextURL = nextURLs[0];
            logger.log(`🚀 1秒后跳转到第1个URL...`, 'success');
            logger.log(`URL: ${nextURL.substring(0, 60)}...`, 'info');
            setTimeout(() => {
                window.location.href = nextURL;
            }, 1000);
        } else {
            logger.log('❌ 没有待处理的URL', 'warning');
        }
    }

    function isBatchMode() {
        // 检查当前URL是否在队列中
        const currentURL = window.location.href;
        
        // 必须是Stripe支付页面
        if (!currentURL.includes('checkout.stripe.com/c/pay/')) {
            return false;
        }
        
        // 检查队列中是否有匹配的processing状态URL
        const inQueue = urlQueue.queue.urls.some(item => {
            // 提取pay/后面的ID进行匹配
            const itemMatch = item.url.match(/\/pay\/([^\/\?]+)/);
            const currentMatch = currentURL.match(/\/pay\/([^\/\?]+)/);
            
            if (itemMatch && currentMatch) {
                return itemMatch[1] === currentMatch[1] && item.status === 'processing';
            }
            return false;
        });
        
        return inQueue;
    }

    // ===== 跳转到下一个URL =====
    async function jumpToNextURL() {
        // 1. 标记当前URL完成
        const currentURL = window.location.href;
        const currentMatch = currentURL.match(/\/pay\/([^\/\?]+)/);
        
        if (currentMatch) {
            const targetItem = urlQueue.queue.urls.find(item => {
                const itemMatch = item.url.match(/\/pay\/([^\/\?]+)/);
                return itemMatch && itemMatch[1] === currentMatch[1];
            });
            
            if (targetItem) {
                targetItem.status = 'completed';
                urlQueue.save();
                logger.log(`✓ URL已标记为完成: ${targetItem.url.substring(0, 50)}...`, 'success');
                
                // 从文本框删除
                updateTextareaWithPendingURLs();
            }
        }
        
        // 2. 获取下一个URL
        const stats = urlQueue.getStats();
        logger.log(`进度: ${stats.completed}/${stats.total} 完成`, 'info');
        
        const nextURLs = urlQueue.getNext(1);
        
        if (nextURLs.length > 0) {
            const nextURL = nextURLs[0];
            logger.log(`⏭️ 立即跳转到下一个URL...`, 'success');
            logger.log(`下一个: ${nextURL.substring(0, 60)}...`, 'info');
            
            // 直接跳转（不关闭标签页）
            window.location.href = nextURL;
        } else {
            // 全部完成
            logger.log('========== 🎉 全部URL处理完成！ ==========', 'success');
            logger.log(`✅ 共完成 ${stats.completed} 个URL`, 'success');
        }
    }

    // ===== 后台执行保活机制 =====
    function keepAlive() {
        // 防止后台标签页被浏览器暂停
        // 使用多种策略保持脚本活跃
        
        // 1. 定时发送console日志（轻量级）
        setInterval(() => {
            console.log('[Cursor Auto Fill] Keepalive ping:', new Date().toLocaleTimeString());
        }, 10000);
        
        // 2. 使用requestAnimationFrame保持活跃
        function rafKeepAlive() {
            requestAnimationFrame(rafKeepAlive);
        }
        rafKeepAlive();
        
        // 3. 监听visibilitychange事件
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                console.log('[Cursor Auto Fill] 标签页进入后台，继续执行...');
            } else {
                console.log('[Cursor Auto Fill] 标签页回到前台');
            }
        });
        
        logger.log('✓ 后台保活机制已启动', 'info');
    }

    // ===== 检测页面类型 =====
    function getPageType() {
        const url = window.location.href;
        if (url.includes('checkout.stripe.com/c/pay/')) {
            return 'stripe';
        } else if (url.includes('cursor.com') || url.includes('google.com') || url.includes('baidu.com')) {
            return 'config';
        }
        return 'other';
    }

    // ===== 创建配置专用UI（简化版）=====
    function createConfigOnlyUI() {
        const oldUI = document.getElementById('cursor-auto-fill-container');
        if (oldUI) {
            oldUI.remove();
        }

        const container = document.createElement('div');
        container.id = 'cursor-auto-fill-container';
        
        container.innerHTML = `
            <div id="cursor-auto-fill-panel" style="position: fixed !important; top: 24px !important; right: 24px !important; max-width: 420px !important; min-width: 360px !important; width: auto !important; background: #ffffff !important; border-radius: 20px !important; box-shadow: 0 24px 48px rgba(0, 0, 0, 0.1), 0 0 0 1px rgba(0, 0, 0, 0.05) !important; z-index: 2147483647 !important; overflow: visible !important;">
                <div id="cursor-auto-fill-header" style="background: #ffffff !important; padding: 24px !important; border-bottom: 1px solid #f0f0f0 !important;">
                    <div style="display: flex !important; justify-content: space-between !important; align-items: center !important; margin-bottom: 12px !important;">
                        <div style="font-size: 20px !important; font-weight: 700 !important; color: #000000 !important;">Cursor 批量配置</div>
                        <button id="cursor-auto-fill-toggle" style="background: #f5f5f5 !important; border: none !important; color: #666 !important; width: 36px !important; height: 36px !important; border-radius: 10px !important; cursor: pointer !important; font-size: 22px !important;">−</button>
                    </div>
                    <div style="font-size: 13px; color: #666; padding: 6px 12px; background: #f9f9f9; border-radius: 8px;">📍 当前页面：配置模式</div>
                </div>
                <div id="cursor-auto-fill-content" style="padding: 20px 24px 24px !important; background: #fafafa !important;">
                    <div class="cursor-section" style="background: #ffffff !important; border-radius: 16px !important; padding: 20px !important; margin-bottom: 16px !important; border: 1px solid #e8e8e8 !important;">
                        <div class="cursor-section-title" style="color: #000000 !important; font-size: 15px !important; font-weight: 600 !important; margin-bottom: 16px !important; padding-bottom: 12px !important; border-bottom: 1px solid #f5f5f5 !important;">批量URL配置</div>
                        <div style="margin-bottom: 12px;">
                            <label style="color: #666; font-size: 13px; display: block; margin-bottom: 6px;">批量URL（每行一个）</label>
                            <textarea id="cursor-url-batch" placeholder="https://checkout.stripe.com/c/pay/cs_xxx1
https://checkout.stripe.com/c/pay/cs_xxx2
https://checkout.stripe.com/c/pay/cs_xxx3
...
粘贴你的URL列表" style="width: 100%; height: 200px; padding: 12px; border: 1.5px solid #e0e0e0; border-radius: 8px; font-family: monospace; font-size: 12px; resize: vertical;"></textarea>
                        </div>
                        <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 12px;">
                            <button id="cursor-batch-start" style="flex: 1; padding: 12px; background: #000; color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px;">🚀 开始批量处理（单页面循环）</button>
                            <button id="cursor-batch-clear" style="padding: 12px 16px; background: #f5f5f5; color: #666; border: none; border-radius: 8px; font-weight: 600; cursor: pointer;">清空</button>
                        </div>
                        <div id="cursor-batch-stats" style="font-size: 12px; color: #666; padding: 12px; background: #f9f9f9; border-radius: 6px; display: none;">
                            <div style="font-weight: 600; margin-bottom: 6px;">处理进度：</div>
                            <div>总数: <span id="stat-total" style="font-weight: 600; color: #000;">0</span> | 完成: <span id="stat-completed" style="font-weight: 600; color: #34C759;">0</span> | 处理中: <span id="stat-processing" style="font-weight: 600; color: #007AFF;">0</span> | 待处理: <span id="stat-pending" style="font-weight: 600; color: #FF9500;">0</span></div>
                        </div>
                    </div>
                    
                    <div class="cursor-section" style="background: #ffffff !important; border-radius: 16px !important; padding: 20px !important; border: 1px solid #e8e8e8 !important;">
                        <div class="cursor-section-title" style="color: #000000 !important; font-size: 15px !important; font-weight: 600 !important; margin-bottom: 16px !important; padding-bottom: 12px !important; border-bottom: 1px solid #f5f5f5 !important;">执行日志</div>
                        <div id="cursor-auto-fill-logs" style="font-family: monospace; font-size: 12px; line-height: 2; max-height: 200px; overflow-y: auto;"></div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(container);
        
        logger.log('✓ 配置面板已创建', 'success');
        logger.log('💡 提示：在此配置URL，脚本会自动打开标签页并处理', 'info');

        // 设置事件
        setupConfigUIEvents();
        makeDraggable();
        logger.updateLogDisplay();
        
        // 加载已有队列
        if (urlQueue.queue.urls.length > 0) {
            document.getElementById('cursor-batch-stats').style.display = 'block';
            updateBatchStats();
            setInterval(updateBatchStats, 2000);
        }
    }

    // ===== 配置UI事件 =====
    function setupConfigUIEvents() {
        // 折叠按钮
        const toggleBtn = document.getElementById('cursor-auto-fill-toggle');
        const content = document.getElementById('cursor-auto-fill-content');
        let isCollapsed = false;

        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            isCollapsed = !isCollapsed;
            content.style.display = isCollapsed ? 'none' : 'block';
            toggleBtn.textContent = isCollapsed ? '+' : '−';
        });

        // 批量处理按钮
        document.getElementById('cursor-batch-start').addEventListener('click', (e) => {
            e.stopPropagation();
            const urlText = document.getElementById('cursor-url-batch').value;
            if (!urlText.trim()) {
                logger.log('⚠️ 请输入URL列表', 'warning');
                return;
            }
            
            const count = urlQueue.addURLs(urlText);
            if (count > 0) {
                document.getElementById('cursor-batch-stats').style.display = 'block';
                updateBatchStats();
                startBatchProcessing();
            }
        });
        
        // 清空队列按钮
        document.getElementById('cursor-batch-clear').addEventListener('click', (e) => {
            e.stopPropagation();
            urlQueue.clear();
            document.getElementById('cursor-url-batch').value = '';
            document.getElementById('cursor-batch-stats').style.display = 'none';
            logger.log('队列已清空', 'info');
        });
    }

    // ===== 主函数 =====
    async function main() {
        logger.log('✓ 脚本已加载', 'info');
        
        // 检测页面类型
        const pageType = getPageType();
        logger.log(`当前页面类型: ${pageType}`, 'info');
        
        // 立即启动保活机制（后台执行关键）
        keepAlive();

        await sleep(500);
        
        // 根据页面类型创建不同的UI
        if (pageType === 'config') {
            // 配置页面 - 只显示批量配置UI
            createConfigOnlyUI();
            logger.log('🎯 配置模式已启动，请输入URL开始批量处理', 'success');
            return;
        }
        
        // Stripe支付页面 - 显示完整UI
        createUI();

        logger.log('正在检测页面...', 'info');
        
        // 检查页面可见性状态
        const isHidden = document.hidden;
        if (isHidden) {
            logger.log('⚠️ 检测到标签页在后台，强制执行模式已启用', 'warning');
        }
        
        const isCursor = await waitForPageLoad();

        if (!isCursor) {
            logger.log('这不是 Cursor 试用页面，脚本待机中', 'warning');
            return;
        }

        // 检查是否是批量模式
        const batchMode = isBatchMode();
        
        // 等待0.5秒让页面内容完全加载
        await sleep(500);
        
        // 检查页面是否已经完成支付（已使用的URL）
        const alreadyCompleted = isAlreadyCompleted();
        if (alreadyCompleted) {
            logger.log('========== 检测到此URL已被使用 ==========', 'warning');
            logger.log('⏭️ 跳过填写，直接跳转下一个', 'info');
            
            if (batchMode) {
                // 批量模式下，直接跳转下一个
                await sleep(1000);
                await jumpToNextURL();
            } else {
                logger.log('此URL无需处理，已经使用过了', 'warning');
            }
            return;
        }
        
        if (config.autoFill || batchMode) {
            const mode = batchMode ? '批量模式' : '自动填写';
            const delay = 0; // 立即开始，不等待
            
            logger.log(`${mode}：立即开始...`, 'info');
            
            // 使用setImmediate或setTimeout
            setTimeout(async () => {
                logger.log('========== 自动开始填写 ==========', 'info');
                logger.log(`当前标签页状态: ${document.hidden ? '后台' : '前台'}`, 'info');
                
                // 重试逻辑：最多重试3次
                let retryCount = 0;
                const maxRetries = 3;
                let success = false;
                
                while (retryCount < maxRetries && !success) {
                    if (retryCount > 0) {
                        logger.log(`========== 第 ${retryCount + 1} 次尝试 ==========`, 'warning');
                    }
                    
                    try {
                        success = await fillForm();
                        
                        if (!success && retryCount < maxRetries - 1) {
                            logger.log(`⚠️ 支付失败，2秒后重新生成卡号并重试...`, 'warning');
                            await sleep(2000);
                            retryCount++;
                        } else if (!success) {
                            logger.log(`❌ 已重试 ${maxRetries} 次，全部失败`, 'error');
                            if (batchMode) {
                                logger.log('跳过该URL，3秒后继续下一个...', 'warning');
                                await sleep(3000);
                                await jumpToNextURL();
                            }
                        } else {
                            // 成功，fillForm内部已经处理了跳转逻辑
                        }
                    } catch (error) {
                        logger.log(`执行出错: ${error.message}`, 'error');
                        
                        if (batchMode) {
                            logger.log('⚠️ 发生错误，3秒后跳过该URL，继续下一个...', 'warning');
                            await sleep(3000);
                            await jumpToNextURL();
                        }
                        break;
                    }
                }
            }, delay);
        } else {
            logger.log('自动填写未启用，请点击"开始填写"按钮', 'info');
        }
        
        // 如果有队列，定时更新统计
        if (urlQueue.queue.urls.length > 0) {
            document.getElementById('cursor-batch-stats').style.display = 'block';
            updateBatchStats();
            setInterval(updateBatchStats, 2000);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', main);
    } else {
        main();
    }

})();
