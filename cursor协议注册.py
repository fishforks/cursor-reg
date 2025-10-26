#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cursor 自动注册并激活Pro - 最终版（使用随机邮箱）

BY： 652617835
"""

try:
    from curl_cffi import requests
    HAS_CURL_CFFI = True
    print('[OK] 已加载curl_cffi，可绕过Cloudflare')
except ImportError:
    import requests
    HAS_CURL_CFFI = False
    print('[警告] 未安装curl_cffi，可能被Cloudflare拦截')
    print('[安装] pip install curl_cffi')
    print()

import json
import time
import uuid
import logging
import os
import re
import random
import string
import configparser
from typing import Dict, Optional
from datetime import datetime
from urllib.parse import urlencode, parse_qs, urlparse, quote


# ==================== 邮箱域名黑名单管理 ====================

import threading
BLACKLIST_FILE = 'email_domain_blacklist.txt'
blacklist_lock = threading.RLock()  # ✅ 使用可重入锁，避免死锁

def load_domain_blacklist(debug: bool = False) -> set:
    """加载域名黑名单（线程安全，每次都从文件实时读取）

    Args:
        debug: 是否输出调试信息
    """
    try:
        with blacklist_lock:
            if os.path.exists(BLACKLIST_FILE):
                with open(BLACKLIST_FILE, 'r', encoding='utf-8') as f:
                    domains = {line.strip() for line in f if line.strip()}
                    if debug and domains:
                        import builtins
                        real_print = getattr(builtins, '__original_print__', print)
                        real_print(f'[调试] 读取黑名单: {len(domains)}个域名 - {", ".join(sorted(domains))}')
                    return domains
            return set()
    except Exception as e:
        import builtins
        real_print = getattr(builtins, '__original_print__', print)
        real_print(f'[黑名单] 加载失败: {e}')
        return set()

def add_to_blacklist(email: str):
    """将邮箱域名添加到黑名单（线程安全，立即写入）

    Args:
        email: 邮箱地址，如 test@example.com
    """
    try:
        # 提取域名
        if '@' not in email:
            return

        domain = email.split('@')[1].lower()

        with blacklist_lock:
            # 加载现有黑名单
            blacklist = load_domain_blacklist()

            # 如果已存在，不重复添加
            if domain in blacklist:
                return

            # ✅ 关键：立即写入并刷新到磁盘
            with open(BLACKLIST_FILE, 'a', encoding='utf-8') as f:
                f.write(f'{domain}\n')
                f.flush()  # 强制刷新缓冲区
                os.fsync(f.fileno())  # 确保写入磁盘

            # ✅ 使用 original_print 在批量模式下也能看到输出
            import builtins
            real_print = getattr(builtins, '__original_print__', print)
            real_print(f'\n[黑名单] 已添加域名: {domain}（立即生效）')
            real_print(f'[原因] 触发手机验证，后续线程将避免使用此域名')
            real_print()
    except Exception as e:
        import builtins
        real_print = getattr(builtins, '__original_print__', print)
        real_print(f'[黑名单] 添加失败: {e}')

def is_domain_blacklisted(domain: str) -> bool:
    """检查域名是否在黑名单中

    Args:
        domain: 域名，如 example.com

    Returns:
        True 如果在黑名单中
    """
    blacklist = load_domain_blacklist()
    return domain.lower() in blacklist

# ==================== 读取配置文件 ====================

def load_config():
    """从 config.ini 读取配置"""
    config = configparser.ConfigParser()
    config_file = 'config.ini'
    
    if os.path.exists(config_file):
        config.read(config_file, encoding='utf-8')
        print(f'[配置] 已加载 {config_file}')
        return config
    else:
        print(f'[警告] 未找到 {config_file}，使用默认配置')
        return None

CONFIG = load_config()

# 从配置文件读取邮件服务配置
EMAIL_SERVICE = 'tmpmail'  # 默认使用 tmpmail
if CONFIG and 'email' in CONFIG:
    EMAIL_SERVICE = CONFIG['email'].get('service', 'tmpmail').lower()
    print(f'[邮件服务] 使用: {EMAIL_SERVICE}')

# 从配置文件读取tmpmail配置
if CONFIG and 'server' in CONFIG:
    TMPMAIL_API_KEY = CONFIG['server'].get('api_key', '')
    TMPMAIL_BASE_URL = CONFIG['server'].get('base_url', 'https://www.tmpmail.vip')
    if EMAIL_SERVICE == 'tmpmail':
        print(f'[tmpmail] API Key: {TMPMAIL_API_KEY[:20]}...')
        print(f'[tmpmail] Base URL: {TMPMAIL_BASE_URL}')
else:
    TMPMAIL_API_KEY = ''
    TMPMAIL_BASE_URL = 'https://www.tmpmail.vip'
    if EMAIL_SERVICE == 'tmpmail':
        print('[警告] config.ini 中未找到 tmpmail 配置')

# 从配置文件读取gptmail配置
if CONFIG and 'gptmail' in CONFIG:
    GPTMAIL_BASE_URL = CONFIG['gptmail'].get('base_url', 'https://mail.chatgpt.org.uk')
    if EMAIL_SERVICE == 'gptmail':
        print(f'[gptmail] Base URL: {GPTMAIL_BASE_URL}')
else:
    GPTMAIL_BASE_URL = 'https://mail.chatgpt.org.uk'
    if EMAIL_SERVICE == 'gptmail':
        print('[警告] config.ini 中未找到 gptmail 配置，使用默认值')

# ======================================================


def generate_random_email() -> str:
    """生成随机邮箱（使用多种后缀域名，实时过滤黑名单）"""
    # 随机用户名（8-12位字母数字）
    username_length = random.randint(8, 12)
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=username_length))

    # 使用多种后缀的临时邮箱域名
    all_domains = [
        # .com 域名
        'guerrillamail.com',
        'sharklasers.com',
        'pokemail.com',
        'spam4.com',
        'grr.la',
        'guerrillamailblock.com',
        # .net 域名
        'guerrillamail.net',
        'guerrillamail.org',
        # 其他后缀
        'guerrillamail.biz',
        'guerrillamail.de',
        'spam4.me',
        'grrmailblock.com',
    ]

    # ✅ 实时加载最新黑名单（每次调用都重新读取文件）
    blacklist = load_domain_blacklist()
    available_domains = [d for d in all_domains if d not in blacklist]

    if not available_domains:
        import builtins
        real_print = getattr(builtins, '__original_print__', print)
        real_print('[警告] 所有域名都在黑名单中！使用原域名列表')
        available_domains = all_domains

    domain = random.choice(available_domains)
    email = f'{username}@{domain}'

    return email


def random_delay(min_seconds: float = 1.0, max_seconds: float = 5.0):
    """添加随机延迟，模拟真实用户行为
    
    Args:
        min_seconds: 最小延迟（秒）
        max_seconds: 最大延迟（秒）
    """
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def generate_random_fingerprint() -> Dict[str, str]:
    """生成随机浏览器指纹，模拟真实用户"""
    
    # 随机浏览器版本（使用较新但不是最新的版本）
    chrome_versions = ['120', '121', '122', '123']
    chrome_ver = random.choice(chrome_versions)
    chrome_full = f'{chrome_ver}.0.{random.randint(6000, 6500)}.{random.randint(100, 200)}'
    
    # 随机操作系统（倾向于Windows 10）
    os_choices = [
        ('Windows NT 10.0; Win64; x64', 'Win32', 0.5),
        ('Windows NT 11.0; Win64; x64', 'Win32', 0.2),
        (f'Macintosh; Intel Mac OS X 10_15_{random.randint(5, 7)}', 'MacIntel', 0.2),
        (f'Macintosh; Intel Mac OS X 13_{random.randint(0, 6)}', 'MacIntel', 0.1),
    ]
    
    # 加权随机选择
    rand = random.random()
    cumulative = 0
    for os_string, platform, weight in os_choices:
        cumulative += weight
        if rand < cumulative:
            selected_os = os_string
            selected_platform = platform
            break
    
    # 随机User-Agent
    user_agent = (
        f'Mozilla/5.0 ({selected_os}) '
        f'AppleWebKit/537.36 (KHTML, like Gecko) '
        f'Chrome/{chrome_full} Safari/537.36'
    )
    
    # 随机屏幕分辨率（常见分辨率）
    resolutions = [
        ('1920x1080', 0.4),
        ('2560x1440', 0.2),
        ('1366x768', 0.15),
        ('1440x900', 0.15),
        ('1536x864', 0.1),
    ]
    rand = random.random()
    cumulative = 0
    for resolution, weight in resolutions:
        cumulative += weight
        if rand < cumulative:
            screen_resolution = resolution
            break
    
    # 随机时区（主要英语国家）
    timezones = [
        ('-480', 0.2),  # PST (美西)
        ('-300', 0.3),  # EST (美东)
        ('-360', 0.2),  # CST (美中)
        ('0', 0.15),    # GMT (英国)
        ('-420', 0.15), # MST (美山地)
    ]
    rand = random.random()
    cumulative = 0
    for tz, weight in timezones:
        cumulative += weight
        if rand < cumulative:
            timezone = tz
            break
    
    # 随机语言（主要英语）
    languages = [
        ('en-US,en;q=0.9', 0.6),
        ('en-GB,en;q=0.9', 0.2),
        ('en-US,en;q=0.9,zh-CN;q=0.8', 0.15),
        ('en-US,en;q=0.9,ja;q=0.8', 0.05),
    ]
    rand = random.random()
    cumulative = 0
    for lang, weight in languages:
        cumulative += weight
        if rand < cumulative:
            accept_language = lang
            break
    
    # Canvas指纹噪音
    canvas_noise = ''.join(random.choices(string.hexdigits.lower(), k=32))
    
    # WebGL vendor/renderer（常见组合）
    webgl_vendors = [
        ('Intel Inc.', 'Intel(R) UHD Graphics 630'),
        ('NVIDIA Corporation', 'NVIDIA GeForce RTX 3060'),
        ('NVIDIA Corporation', 'NVIDIA GeForce GTX 1660'),
        ('AMD', 'AMD Radeon RX 580'),
    ]
    webgl_vendor, webgl_renderer = random.choice(webgl_vendors)
    
    # 硬件并发（CPU核心数）
    hardware_concurrency = random.choice([4, 8, 12, 16])
    
    # 设备内存（GB）
    device_memory = random.choice([4, 8, 16])
    
    return {
        'user_agent': user_agent,
        'screen_resolution': screen_resolution,
        'timezone': timezone,
        'accept_language': accept_language,
        'platform': selected_platform,
        'chrome_version': chrome_ver,
        'canvas_noise': canvas_noise,
        'webgl_vendor': webgl_vendor,
        'webgl_renderer': webgl_renderer,
        'hardware_concurrency': hardware_concurrency,
        'device_memory': device_memory,
    }


# ==================== 配置区 ====================

# 使用tmpmail.vip API（自动获取临时邮箱）
USE_RANDOM_EMAIL = False  # 设置为False使用tmpmail.vip API获取真实临时邮箱
REQUIRE_COM_DOMAIN = False  # 是否强制要求.com后缀（False=接受任何后缀，如.icu）
# tmpmail配置从 config.ini 文件读取
USE_PROXY = False          # 使用代理（推荐）
# 2captcha API配置（Turnstile验证）
CAPTCHA_API_KEY = ''

# ==================== 手机验证（已禁用）====================
# 注意：手机验证功能已禁用，触发手机验证时会直接跳过
# 建议使用代理避免触发手机验证
# 以下配置保留但不会使用

# 5sim API配置（手机验证 - 已禁用）
FIVESIM_API_KEY = ''
FIVESIM_API_BASE = ''
FIVESIM_PRODUCT = 'any'  # 'any' = 任意服务，最便宜
# ========================================================

# Pro订阅配置
PLAN = 'pro'           # 'pro' 或 'business'
INTERVAL = 'monthly'   # 'monthly' ($20/月) 或 'annual' ($200/年)

# 是否激活Pro（必须绑卡才能使用Pro功能）
ACTIVATE_PRO = False   # False=只注册账号并生成订阅链接（推荐：使用浏览器自动化），True=HTTP协议支付（可能失败）

# 闪臣代理API配置
PROXY_API_URL = ''
USE_PROXY = True  # 是否使用代理（强烈建议开启！可避免触发手机验证）

# ================================================


def get_proxy_ip(api_url: str = None, logger = None) -> Optional[str]:
    """获取闪臣代理IP
    
    Args:
        api_url: 代理API URL
        logger: 日志记录器
    
    Returns:
        'http://ip:port' 格式的代理地址
    """
    try:
        import requests as http
        
        if not api_url:
            api_url = ''
        
        if logger:
            logger.info('[代理] 获取代理IP...')
        
        print('[闪臣代理] 获取代理IP...')
        
        resp = http.get(api_url, timeout=30)
        
        if resp.status_code == 200:
            result = resp.text.strip()
            
            # 检查是否是错误
            if result.startswith('error'):
                print(f'[代理] 获取失败: {result}')
                if logger:
                    logger.error(f'代理获取失败: {result}')
                return None
            
            # 格式: IP:port
            if ':' in result:
                proxy_url = f'http://{result}'
                print(f'[代理] 成功: {result}')
                
                if logger:
                    logger.success(f'代理IP: {result}')
                
                return proxy_url
            else:
                print(f'[代理] 格式错误: {result}')
                return None
        else:
            print(f'[代理] 请求失败: {resp.status_code}')
            if logger:
                logger.error(f'代理请求失败: {resp.status_code}')
            return None
        
    except Exception as e:
        print(f'[代理] 异常: {e}')
        if logger:
            logger.error(f'代理异常: {e}')
        return None


def get_5sim_number(api_key: str, product: str = 'other', logger = None) -> Optional[Dict]:
    """购买5sim号码（自动选择最便宜）
    
    参考: https://5sim.net/docs#user
    """
    try:
        import requests as http
        
        if logger:
            logger.info('[5sim] 获取手机号码...')
        
        print('\n[5sim] 正在获取手机号码...')
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json'
        }
        
        # 1. 获取价格和库存
        prices_url = 'https://5sim.net/v1/guest/prices'
        resp_prices = http.get(prices_url, timeout=30)
        
        if resp_prices.status_code != 200:
            print('[5sim] 获取价格失败')
            return None
        
        prices_data = resp_prices.json()
        
        # 找最便宜且有库存的
        best = None
        best_price = float('inf')
        
        for country_code, country_data in prices_data.items():
            if isinstance(country_data, dict) and product in country_data:
                for operator_name, operator_data in country_data[product].items():
                    if isinstance(operator_data, dict):
                        cost = float(operator_data.get('cost', 999))
                        count = int(operator_data.get('count', 0))
                        
                        if count > 0 and cost < best_price:
                            best_price = cost
                            best = {
                                'country': country_code,
                                'operator': operator_name,
                                'price': cost,
                                'count': count
                            }
        
        if not best:
            print('[5sim] 无库存')
            return None
        
        print(f'[5sim] 选择: {best["country"]}/{best["operator"]} - {best["price"]} RUB')
        
        # 2. 购买号码
        buy_url = f'https://5sim.net/v1/user/buy/activation/{best["country"]}/{best["operator"]}/{product}'
        
        resp = http.get(buy_url, headers=headers, timeout=30)
        
        if resp.status_code != 200 or resp.text == 'no free phones':
            print(f'[5sim] 购买失败: {resp.text}')
            return None
        
        result = resp.json()
        
        if 'id' in result and 'phone' in result:
            order_id = str(result['id'])
            phone = str(result['phone'])
            
            if not phone.startswith('+'):
                phone = f'+{phone}'
            
            print(f'[5sim] 成功！号码: {phone}')
            
            if logger:
                logger.success(f'5sim号码: {phone}')
                logger.info(f'订单ID: {order_id}')
            
            return {
                'id': order_id,
                'phone': phone,
                'country': best['country']
            }
        
        return None
        
    except Exception as e:
        print(f'[5sim] 异常: {e}')
        return None


def get_5sim_code(api_key: str, order_id: str, logger = None, timeout: int = 300) -> Optional[str]:
    """获取5sim验证码"""
    try:
        import requests as http
        
        if logger:
            logger.info('[5sim] 等待短信...')
        
        print('\n[5sim] 等待短信...')
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json'
        }
        
        check_url = f'https://5sim.net/v1/user/check/{order_id}'
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            resp = http.get(check_url, headers=headers, timeout=30)
            
            if resp.status_code == 200:
                result = resp.json()
                sms_list = result.get('sms', [])
                
                if sms_list:
                    code = sms_list[0].get('code')
                    if code:
                        elapsed = int(time.time() - start_time)
                        print(f'\n[5sim] 收到短信！耗时: {elapsed}秒')
                        print(f'[5sim] 验证码: {code}')
                        
                        if logger:
                            logger.success(f'5sim验证码: {code}')
                        
                        return code
                
                elapsed = int(time.time() - start_time)
                print(f'\r[5sim] 等待... {elapsed}秒', end='', flush=True)
            
            time.sleep(10)
        
        print('\n[5sim] 超时')
        return None
        
    except Exception as e:
        print(f'\n[5sim] 异常: {e}')
        return None


def cancel_5sim_order(api_key: str, order_id: str):
    """取消5sim订单"""
    try:
        import requests as http
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json'
        }
        
        http.get(f'https://5sim.net/v1/user/cancel/{order_id}', headers=headers, timeout=10)
    except:
        pass


def get_sms_number(api_key: str, service: str = 'go', api_base: str = None, logger = None) -> Optional[Dict]:
    """获取SMS号码（V1 API格式 - 选择最便宜的国家）
    
    参考: https://sms-activate.io/api2
    
    Args:
        api_key: SMS-Activate API密钥
        service: 服务代码（'go' = 其他/Any other）
        api_base: API基础URL
        logger: 日志记录器
    
    Returns:
        {'activation_id': 'xxx', 'phone': '+123456789', 'country': 'XX'}
    """
    try:
        import requests as http
        
        if not api_base:
            api_base = 'https://api.sms-activate.io/stubs/handler_api.php'
        
        if logger:
            logger.info('[SMS] 获取手机号码...')
        
        print('\n[SMS-Activate] 正在获取手机号码...')
        print('[SMS] 服务: 其他（Any other）')
        print('[SMS] 策略: 选择最低价格国家')
        
        # V1 API: 获取价格
        params = {
            'api_key': api_key,
            'action': 'getPrices',
            'service': service
        }
        
        resp = http.get(api_base, params=params, timeout=30)
        
        if resp.status_code != 200:
            print(f'[SMS] 获取价格失败: {resp.status_code}')
            if logger:
                logger.error(f'SMS获取价格失败: {resp.status_code}')
            return None
        
        prices_data = resp.json()
        
        # 解析价格，找最便宜的国家
        # 格式: {"1": {"go": {"cost": 0.3, "count": 90}}, "2": {...}, ...}
        cheapest_country = None
        cheapest_price = float('inf')
        
        for country_code, services in prices_data.items():
            if service in services:
                service_info = services[service]
                cost = float(service_info.get('cost', 999))
                count = int(service_info.get('count', 0))
                
                # 选择有库存且价格最低的
                if count > 0 and cost < cheapest_price:
                    cheapest_price = cost
                    cheapest_country = {
                        'code': country_code,
                        'price': cost,
                        'count': count
                    }
        
        if not cheapest_country:
            print('[SMS] 未找到可用国家（无库存或价格过高）')
            if logger:
                logger.error('SMS无可用国家')
            return None
        
        print(f'[SMS] 选择国家代码: {cheapest_country["code"]}')
        print(f'[SMS] 价格: ${cheapest_price:.3f}')
        print(f'[SMS] 可用号码: {cheapest_country["count"]}个')
        
        if logger:
            logger.info(f'SMS国家: {cheapest_country["code"]} - ${cheapest_price}')
        
        # V1 API: 购买号码
        params = {
            'api_key': api_key,
            'action': 'getNumber',
            'service': service,
            'country': cheapest_country['code']
        }
        
        resp = http.get(api_base, params=params, timeout=30)
        
        if resp.status_code != 200:
            print(f'[SMS] 购买失败: {resp.status_code}')
            if logger:
                logger.error(f'SMS购买失败: {resp.status_code}')
            return None
        
        result = resp.text
        
        # V1 API响应格式: ACCESS_NUMBER:activation_id:phone_number
        # 例如: ACCESS_NUMBER:123456:79123456789
        if result.startswith('ACCESS_NUMBER'):
            parts = result.split(':')
            activation_id = parts[1]
            phone = parts[2]
            
            # 添加+号
            if not phone.startswith('+'):
                phone = f'+{phone}'
            
            print(f'[SMS] 成功！号码: {phone}')
            print(f'[SMS] 激活ID: {activation_id}')
            
            if logger:
                logger.success(f'SMS号码: {phone}')
                logger.info(f'激活ID: {activation_id}')
            
            return {
                'activation_id': activation_id,
                'phone': phone,
                'country': cheapest_country['code']
            }
        else:
            print(f'[SMS] 购买失败: {result}')
            if logger:
                logger.error(f'SMS购买失败: {result}')
            return None
        
    except Exception as e:
        print(f'[SMS] 异常: {e}')
        if logger:
            logger.error(f'SMS异常: {e}')
        import traceback
        traceback.print_exc()
        return None


def get_sms_code(api_key: str, activation_id: str, api_base: str = None, logger = None, timeout: int = 300) -> Optional[str]:
    """获取SMS验证码（V1 API格式）
    
    Args:
        api_key: API密钥
        activation_id: 激活ID
        api_base: API基础URL
        logger: 日志记录器
        timeout: 超时时间（秒）
    
    Returns:
        验证码
    """
    try:
        import requests as http
        
        if not api_base:
            api_base = 'https://api.sms-activate.io/stubs/handler_api.php'
        
        if logger:
            logger.info('[SMS] 等待短信验证码...')
        
        print('\n[SMS-Activate] 等待短信...')
        
        start_time = time.time()
        attempts = 0
        
        while time.time() - start_time < timeout:
            attempts += 1
            
            # V1 API: 获取状态
            params = {
                'api_key': api_key,
                'action': 'getStatus',
                'id': activation_id
            }
            
            resp = http.get(api_base, params=params, timeout=30)
            
            if resp.status_code == 200:
                result = resp.text
                
                # V1 API响应格式
                if result.startswith('STATUS_OK'):
                    # 格式: STATUS_OK:verification_code
                    code = result.split(':')[1] if ':' in result else None
                    
                    if code:
                        elapsed = int(time.time() - start_time)
                        print(f'\n[SMS] 收到短信！耗时: {elapsed}秒')
                        print(f'[SMS] 验证码: {code}')
                        
                        if logger:
                            logger.success(f'SMS验证码: {code}')
                            logger.info(f'等待时长: {elapsed}秒')
                        
                        return code
                
                elif result == 'STATUS_WAIT_CODE':
                    # 等待中
                    elapsed = int(time.time() - start_time)
                    print(f'\r[SMS] 等待中... {elapsed}秒 (尝试{attempts}次)', end='', flush=True)
                
                else:
                    # 其他状态（STATUS_CANCEL等）
                    print(f'\n[SMS] 状态: {result}')
                    if 'CANCEL' in result or 'ERROR' in result:
                        if logger:
                            logger.error(f'SMS状态异常: {result}')
                        return None
            
            time.sleep(10)  # 每10秒检查一次
        
        print(f'\n[SMS] 超时（{timeout}秒）')
        if logger:
            logger.error('SMS超时')
        
        return None
        
    except Exception as e:
        print(f'\n[SMS] 异常: {e}')
        if logger:
            logger.error(f'SMS异常: {e}')
        return None


def cancel_sms_activation(api_key: str, activation_id: str, api_base: str = None):
    """取消SMS激活（V1 API格式）"""
    try:
        import requests as http
        
        if not api_base:
            api_base = 'https://api.sms-activate.io/stubs/handler_api.php'
        
        params = {
            'api_key': api_key,
            'action': 'setStatus',
            'id': activation_id,
            'status': 8  # 8 = 取消激活
        }
        
        http.get(api_base, params=params, timeout=10)
    except:
        pass


def solve_turnstile_2captcha(sitekey: str, page_url: str, api_key: str, logger) -> Optional[str]:
    """使用2captcha解决Cloudflare Turnstile
    
    参考: https://2captcha.com/api-docs/cloudflare-turnstile
    """
    try:
        if logger:
            logger.info('[2captcha] 提交Turnstile任务')
            logger.info(f'[2captcha] Site-Key: {sitekey}')
        
        print('\n[2captcha] 正在自动解决Turnstile验证码...')
        print('[2captcha] 通常需要30-60秒，请耐心等待')
        
        # 使用标准requests库
        import requests as http
        
        # ✅ 关键修复：生成唯一的软ID避免任务冲突
        import uuid
        soft_id = str(int(time.time() * 1000))  # 使用时间戳作为软ID
        
        # 提交任务
        submit_resp = http.post('https://2captcha.com/in.php', data={
            'key': api_key,
            'method': 'turnstile',
            'sitekey': sitekey,
            'pageurl': page_url,
            'soft_id': soft_id,  # ✅ 添加软ID避免冲突
            'json': 1
        }, timeout=30)
        
        submit_result = submit_resp.json()
        
        if submit_result.get('status') != 1:
            error = submit_result.get('request', 'Unknown')
            print(f'[2captcha] 提交失败: {error}')
            if logger:
                logger.error(f'2captcha提交失败: {error}')
            return None
        
        task_id = submit_result.get('request')
        print(f'[2captcha] 任务ID: {task_id} (软ID: {soft_id})')
        
        if logger:
            logger.info(f'[2captcha] 任务ID: {task_id}')
        
        # 轮询结果
        start_time = time.time()
        
        while time.time() - start_time < 120:
            time.sleep(5)
            
            result_resp = http.get('https://2captcha.com/res.php', params={
                'key': api_key,
                'action': 'get',
                'id': task_id,
                'json': 1
            }, timeout=30)
            
            result = result_resp.json()
            
            if result.get('status') == 1:
                token = result.get('request')
                elapsed = int(time.time() - start_time)
                print(f'\n[2captcha] ✓ 成功！耗时: {elapsed}秒')
                
                if logger:
                    logger.success(f'2captcha解答成功，耗时{elapsed}秒')
                    logger.info(f'Token: {token[:80]}...')
                
                return token
            elif result.get('request') == 'CAPCHA_NOT_READY':
                elapsed = int(time.time() - start_time)
                print(f'\r[2captcha] 等待中... {elapsed}秒', end='', flush=True)
            else:
                error = result.get('request', 'Unknown')
                print(f'\n[2captcha] 错误: {error}')
                if logger:
                    logger.error(f'2captcha错误: {error}')
                return None
        
        print('\n[2captcha] 超时')
        if logger:
            logger.error('2captcha超时')
        return None
        
    except Exception as e:
        print(f'\n[2captcha] 异常: {e}')
        if logger:
            logger.error(f'2captcha异常: {e}')
        import traceback
        traceback.print_exc()
        return None


class Logger:
    """日志管理器（线程安全）"""
    
    def __init__(self, log_file: str = None, enable_console: bool = True):
        """
        Args:
            log_file: 日志文件路径
            enable_console: 是否输出到控制台（批量模式建议关闭）
        """
        if log_file is None:
            log_file = f'cursor_auto_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
        # 使用唯一的logger名称（避免多线程冲突）
        import uuid
        logger_name = f'CursorAuto_{uuid.uuid4().hex[:8]}'
        
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.DEBUG)
        
        # 清除可能存在的旧handler
        self.logger.handlers.clear()
        
        # 文件Handler（总是启用）
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        
        # 控制台Handler（可选，批量模式下禁用）
        if enable_console:
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)
        
        self.logger.info(f'日志文件: {log_file}')
    
    def debug(self, msg): self.logger.debug(msg)
    def info(self, msg): self.logger.info(msg)
    def warning(self, msg): self.logger.warning(msg)
    def error(self, msg): self.logger.error(msg)
    def success(self, msg): self.logger.info(f'[OK] {msg}')
    def step(self, num, total, title): 
        self.logger.info('='*60)
        self.logger.info(f'[步骤{num}/{total}] {title}')
        self.logger.info('='*60)


class TempEmail:
    """临时邮箱服务 - tmpmail.vip API"""
    
    def __init__(self, api_key: str, base_url: str, logger: Logger):
        self.api_key = api_key
        self.base_url = base_url
        self.logger = logger
        self.email = None
        
        # 生成随机指纹
        fingerprint = generate_random_fingerprint()
        
        # 使用curl_cffi（如果可用）
        if HAS_CURL_CFFI:
            try:
                self.session = requests.Session(impersonate="chrome120")
            except Exception as e:
                self.logger.info('[fallback] 邮箱服务使用标准requests库')
                import requests as std_requests
                self.session = std_requests.Session()
        else:
            import requests as std_requests
            self.session = std_requests.Session()
        
        # 正确的API Headers（参考临时邮箱系统.py）
        self.session.headers.update({
            'X-API-Key': api_key,  # ✅ 关键：使用 X-API-Key
            'Content-Type': 'application/json',
            'User-Agent': fingerprint['user_agent'],
            'Accept-Language': fingerprint['accept_language']
        })
    
    def get_domains(self) -> Optional[list]:
        """获取可用域名列表
        
        API响应格式：{"domains": ["domain1.com", ...], "count": N}
        """
        try:
            url = f'{self.base_url}/api/domains'
            self.logger.debug(f'[API] GET {url}')
            self.logger.debug(f'[Headers] X-API-Key: {self.api_key[:20]}...')
            
            resp = self.session.get(url, timeout=30)
            
            self.logger.debug(f'[响应] 状态码: {resp.status_code}')
            self.logger.debug(f'[响应] Content-Type: {resp.headers.get("content-type", "N/A")}')
            
            if resp.status_code == 200:
                data = resp.json()
                self.logger.debug(f'[响应数据] {data}')

                # 正确解析API响应
                domains = data.get('domains', [])
                count = data.get('count', 0)

                if domains and len(domains) > 0:
                    self.logger.success(f'[邮箱] ✓ 获取到 {len(domains)} 个可用域名（API返回count={count}）')

                    # 分析域名后缀分布
                    com_count = len([d for d in domains if d.endswith('.com')])
                    net_count = len([d for d in domains if d.endswith('.net')])
                    org_count = len([d for d in domains if d.endswith('.org')])
                    other_count = len(domains) - com_count - net_count - org_count

                    self.logger.info(f'[域名分布] .com: {com_count}, .net: {net_count}, .org: {org_count}, 其他: {other_count}')

                    # 显示部分域名示例
                    sample_domains = domains[:5]
                    self.logger.debug(f'[域名示例] {sample_domains}')

                    return domains
                else:
                    self.logger.error('[邮箱] ✗ API返回空域名列表')
                    self.logger.error(f'[完整响应] {data}')
                    self.logger.error('[原因] 可能是您的账号没有被授权使用任何域名')
                    self.logger.error('[建议] 请联系tmpmail管理员为您的账号授权域名')
                    return None
            elif resp.status_code == 401:
                self.logger.error('[邮箱] ✗ API KEY 无效或未提供')
                self.logger.error(f'[响应] {resp.text[:500]}')
                self.logger.error(f'[检查] API KEY: {self.api_key[:20]}...')
                self.logger.error('[建议] 请检查 config.ini 中的 tmpmail_api_key 是否正确')
                return None
            elif resp.status_code == 403:
                self.logger.error('[邮箱] ✗ API KEY 被禁用或账号被暂停')
                self.logger.error(f'[响应] {resp.text[:500]}')
                self.logger.error('[建议] 请联系tmpmail管理员或在后台重置API KEY')
                return None
            elif resp.status_code == 429:
                self.logger.error('[邮箱] ✗ API 调用频率超限')
                self.logger.error(f'[响应] {resp.text[:500]}')
                self.logger.error('[建议] 请稍后重试或联系管理员提高限制')
                return None
            else:
                self.logger.error(f'[邮箱] ✗ 获取域名失败: HTTP {resp.status_code}')
                self.logger.error(f'[响应体] {resp.text[:500]}')
                self.logger.error(f'[请求URL] {url}')
                self.logger.error(f'[API KEY] {self.api_key[:20]}...')
                return None
        except Exception as e:
            self.logger.error(f'[邮箱] ✗ 获取域名异常: {e}')
            import traceback
            self.logger.debug(traceback.format_exc())
            return None
    
    def create(self, prefer_com: bool = True) -> Optional[str]:
        """创建临时邮箱

        Args:
            prefer_com: 是否优先使用.com后缀域名（默认True）

        API响应格式：
        {
            "email": "xxx@domain.com",
            "username": "xxx",
            "domain": "domain.com",
            "expires_at": "2024-...",
            "quick_access_url": "https://..."
        }
        """
        self.logger.info('[邮箱] 创建临时邮箱...')

        try:
            # ✅ 关键修复：总是获取域名列表（prefer_com 只影响选择逻辑）
            selected_domain = None
            self.logger.info('[邮箱] 正在获取可用域名列表...')
            domains = self.get_domains()

            if domains:
                # 加载黑名单并过滤
                blacklist = load_domain_blacklist()
                if blacklist:
                    self.logger.info(f'[黑名单] 过滤 {len(blacklist)} 个域名')
                    domains = [d for d in domains if d not in blacklist]
                    self.logger.info(f'[过滤后] 剩余 {len(domains)} 个可用域名')

                if not domains:
                    # ✅ 关键修复：所有域名都在黑名单中，直接返回失败
                    self.logger.error('[黑名单] ✗ 所有可用域名都已被拉黑！')
                    self.logger.error('[说明] tmpmail API 的所有域名都在黑名单中')
                    self.logger.error('[建议] 请检查 email_domain_blacklist.txt 文件')

                    # 显示黑名单内容
                    if blacklist:
                        self.logger.error(f'[黑名单] 当前黑名单: {", ".join(sorted(blacklist))}')

                    return None  # 直接返回失败，不要让API随机分配
                else:
                    # ✅ 根据 prefer_com 选择域名
                    if prefer_com:
                        # 优先.com，但如果没有就用其他的
                        com_domains = [d for d in domains if d.endswith('.com')]
                        if com_domains:
                            self.logger.success(f'[邮箱] ✓ 找到 {len(com_domains)} 个.com域名')
                            selected_domain = random.choice(com_domains)
                        else:
                            self.logger.info('[邮箱] 未找到.com域名，使用其他后缀')
                            selected_domain = random.choice(domains)
                    else:
                        # 不限制后缀，从所有域名中随机选择
                        self.logger.info(f'[邮箱] 可用域名: {len(domains)} 个（所有后缀）')
                        selected_domain = random.choice(domains)

                    self.logger.success(f'[邮箱] ✓ 选择域名: {selected_domain}')
            else:
                # ✅ 关键修复：获取域名列表失败，直接返回失败
                self.logger.error('[邮箱] ✗ 获取域名列表失败')
                self.logger.error('[建议] 检查 tmpmail API 是否正常或网络连接')
                return None  # 直接返回失败，不要让API随机分配

            # ✅ 关键：创建邮箱前最后一次检查黑名单（防止时间窗口问题）
            if selected_domain:
                blacklist_final = load_domain_blacklist()
                if blacklist_final:
                    self.logger.debug(f'[黑名单实时检查] 当前黑名单: {blacklist_final}')
                if selected_domain in blacklist_final:
                    self.logger.warning(f'[黑名单] 域名 {selected_domain} 刚被加入黑名单（实时检测），重新选择')
                    # 重新获取并过滤
                    domains = self.get_domains()
                    if domains:
                        domains = [d for d in domains if d not in blacklist_final]
                        if domains:
                            if prefer_com:
                                com_domains = [d for d in domains if d.endswith('.com')]
                                selected_domain = random.choice(com_domains if com_domains else domains)
                            else:
                                selected_domain = random.choice(domains)
                            self.logger.success(f'[邮箱] ✓ 重新选择: {selected_domain}')
                        else:
                            # ✅ 重新过滤后没有可用域名，直接返回失败
                            self.logger.error('[黑名单] ✗ 所有域名都已被拉黑（实时检测）')
                            self.logger.error(f'[黑名单] 当前黑名单: {", ".join(sorted(blacklist_final))}')
                            return None
                    else:
                        # ✅ 重新获取域名列表失败，直接返回失败
                        self.logger.error('[邮箱] ✗ 重新获取域名列表失败')
                        return None
                else:
                    self.logger.debug(f'[黑名单检查] {selected_domain} 不在黑名单中，可以使用')

            # ✅ 最终检查：确保有选定的域名
            if not selected_domain:
                self.logger.error('[邮箱] ✗ 没有可用域名')
                return None

            url = f'{self.base_url}/api/mailbox'

            # 构造请求体（参考临时邮箱系统.py）
            payload = {'expiry_days': 1}  # 默认1天有效期
            payload['domain'] = selected_domain  # ✅ 总是指定域名，不让API随机分配
            self.logger.info(f'[请求] 指定域名: {selected_domain}')
            
            self.logger.debug(f'[API] POST {url}')
            self.logger.debug(f'[Headers] X-API-Key: {self.api_key[:20]}...')
            self.logger.debug(f'[Payload] {payload}')
            
            resp = self.session.post(url, json=payload, timeout=30)
            
            self.logger.debug(f'[响应] 状态码: {resp.status_code}')
            self.logger.debug(f'[响应] Content-Type: {resp.headers.get("content-type", "N/A")}')
            
            if resp.status_code == 200:
                data = resp.json()
                self.logger.debug(f'[响应数据] {data}')
                
                # 正确解析API响应
                self.email = data.get('email')
                username = data.get('username')
                domain = data.get('domain')
                expires_at = data.get('expires_at')
                quick_access_url = data.get('quick_access_url')

                if not self.email:
                    self.logger.error('[邮箱] ✗ 响应中缺少email字段')
                    self.logger.debug(f'[完整响应] {data}')
                    return None

                # ✅ 关键：检查API返回的域名是否在黑名单中
                if domain:
                    blacklist_check = load_domain_blacklist()
                    if domain in blacklist_check:
                        self.logger.warning(f'[黑名单] ✗ API返回的域名 {domain} 在黑名单中！')
                        self.logger.warning(f'[邮箱] {self.email}')
                        self.logger.info(f'[处理] 删除该邮箱并重新尝试')

                        # 删除该邮箱
                        try:
                            delete_url = f'{self.base_url}/api/mailbox/{self.email}'
                            self.session.delete(delete_url, timeout=10)
                            self.logger.debug('[删除] 已删除黑名单域名邮箱')
                        except:
                            pass

                        self.email = None

                        # 重新尝试创建（递归调用，但限制次数）
                        if not hasattr(self, '_retry_count'):
                            self._retry_count = 0

                        self._retry_count += 1
                        if self._retry_count <= 3:
                            self.logger.info(f'[重试] 第 {self._retry_count} 次尝试创建非黑名单邮箱')
                            time.sleep(1)  # 等待1秒
                            return self.create(prefer_com=prefer_com)
                        else:
                            self.logger.error('[失败] 重试3次后仍无法获取非黑名单邮箱')
                            self.logger.error('[建议] 可能所有tmpmail域名都已被拉黑，请检查黑名单文件')
                            return None

                # 显示邮箱信息
                if prefer_com and domain:
                    if domain.endswith('.com'):
                        self.logger.success(f'✓✓✓ 邮箱创建成功: {self.email}')
                        self.logger.success(f'    域名: {domain} (.com ✓)')
                    else:
                        self.logger.success(f'✓ 邮箱创建成功: {self.email}')
                        self.logger.info(f'    域名: {domain}')
                        if selected_domain and selected_domain != domain:
                            self.logger.info(f'    [说明] API使用了可用域名（{selected_domain}不可用）')
                else:
                    self.logger.success(f'✓ 邮箱创建成功: {self.email}')

                # 显示详细信息
                self.logger.info(f'    用户名: {username}')
                self.logger.info(f'    过期时间: {expires_at}')
                if quick_access_url:
                    self.logger.debug(f'    快速访问: {quick_access_url}')

                # ✅ 重置重试计数（成功创建邮箱）
                if hasattr(self, '_retry_count'):
                    delattr(self, '_retry_count')

                return self.email
            else:
                self.logger.error(f'✗ 创建失败: HTTP {resp.status_code}')
                self.logger.debug(f'[响应体] {resp.text[:500]}')
                return None
        except Exception as e:
            self.logger.error(f'✗ 创建异常: {e}')
            import traceback
            self.logger.debug(traceback.format_exc())
            return None
    
    def get_verification_code(self, timeout: int = 60) -> Optional[str]:
        """获取验证码（使用tmpmail.vip的/code API）

        Args:
            timeout: 超时时间（秒），默认60秒
        """
        self.logger.info('[邮箱] 等待验证码...')

        from urllib.parse import quote

        start_time = time.time()
        attempts = 0
        max_attempts = timeout // 5  # 每5秒检查一次
        
        # 使用tmpmail.vip的专用验证码API
        encoded_email = quote(self.email)
        code_url = f'{self.base_url}/api/mailbox/{encoded_email}/code'
        
        self.logger.debug(f'[API] {code_url}')
        
        while time.time() - start_time < timeout:
            attempts += 1
            
            try:
                # 直接调用/code API获取验证码
                resp = self.session.get(code_url, timeout=30)
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    # API返回格式: {"found": true, "code": "123456"}
                    if data.get('found'):
                        code = data.get('code')
                        if code and code.isdigit() and len(code) == 6:
                            self.logger.success(f'验证码: {code}')
                            self.logger.info(f'尝试次数: {attempts}')
                            return code
                    
                    self.logger.debug(f'[尝试{attempts}] 验证码尚未到达')
                else:
                    self.logger.debug(f'[API] 状态码: {resp.status_code}')
                
                time.sleep(5)
                
            except Exception as e:
                self.logger.debug(f'获取异常: {e}')
                time.sleep(5)
        
        self.logger.error(f'超时未收到验证码（尝试了{attempts}次）')
        return None
    
    def delete(self):
        """删除邮箱"""
        if self.email:
            try:
                url = f'{self.base_url}/api/mailbox/{self.email}'
                self.session.delete(url, timeout=30)
                self.logger.info(f'[邮箱] 已删除: {self.email}')
            except:
                pass


class GPTMailClient:
    """GPTMail 邮箱服务 - mail.chatgpt.org.uk"""

    def __init__(self, base_url: str, logger: Logger):
        self.base_url = base_url
        self.logger = logger
        self.email = None

        # 生成随机指纹
        fingerprint = generate_random_fingerprint()

        # 使用curl_cffi（如果可用）
        if HAS_CURL_CFFI:
            try:
                self.session = requests.Session(impersonate="chrome120")
            except Exception as e:
                self.logger.info('[fallback] GPTMail使用标准requests库')
                import requests as std_requests
                self.session = std_requests.Session()
        else:
            import requests as std_requests
            self.session = std_requests.Session()

        # 设置请求头
        self.session.headers.update({
            'User-Agent': fingerprint['user_agent'],
            'Accept': 'application/json',
            'Accept-Language': fingerprint['accept_language'],
            'Referer': base_url + '/'
        })

    def create(self, prefer_com: bool = True) -> Optional[str]:
        """创建临时邮箱

        Args:
            prefer_com: 忽略（GPTMail不支持选择域名）

        Returns:
            邮箱地址
        """
        self.logger.info('[GPTMail] 创建临时邮箱...')

        try:
            url = f'{self.base_url}/api/generate-email'

            self.logger.debug(f'[API] GET {url}')

            resp = self.session.get(url, timeout=30)

            self.logger.debug(f'[响应] 状态码: {resp.status_code}')

            if resp.status_code == 200:
                data = resp.json()
                self.email = data.get('email')

                if not self.email:
                    self.logger.error('[GPTMail] 响应中缺少email字段')
                    self.logger.debug(f'[完整响应] {data}')
                    return None

                self.logger.success(f'✓ GPTMail邮箱创建成功: {self.email}')

                # 提取域名
                domain = self.email.split('@')[1] if '@' in self.email else 'unknown'
                self.logger.info(f'    域名: {domain}')

                return self.email
            else:
                self.logger.error(f'✗ 创建失败: HTTP {resp.status_code}')
                self.logger.debug(f'[响应体] {resp.text[:500]}')
                return None
        except Exception as e:
            self.logger.error(f'✗ 创建异常: {e}')
            import traceback
            self.logger.debug(traceback.format_exc())
            return None

    def get_verification_code(self, timeout: int = 60) -> Optional[str]:
        """获取验证码

        Args:
            timeout: 超时时间（秒）

        Returns:
            验证码
        """
        self.logger.info('[GPTMail] 等待验证码...')

        if not self.email:
            self.logger.error('[GPTMail] 邮箱未创建')
            return None

        from urllib.parse import quote

        start_time = time.time()
        check_interval = 3  # 每3秒检查一次

        while time.time() - start_time < timeout:
            try:
                # 获取邮件列表
                encoded_email = quote(self.email)
                url = f'{self.base_url}/api/get-emails?email={encoded_email}'

                resp = self.session.get(url, timeout=30)

                if resp.status_code == 200:
                    data = resp.json()
                    emails = data.get('emails', [])

                    if emails:
                        # 检查每封邮件
                        for email_item in emails:
                            # 检查是否是验证邮件
                            if self._is_verification_email(email_item):
                                # 优先使用HTML内容
                                content = email_item.get('htmlContent', '') or email_item.get('content', '')

                                # 提取验证码（使用正则提取6位数字验证码）
                                code = self._extract_code(content)

                                if code:
                                    elapsed = int(time.time() - start_time)
                                    self.logger.success(f'验证码: {code}')
                                    self.logger.info(f'耗时: {elapsed}秒')
                                    return code

                # 等待后重试
                self.logger.debug(f'[尝试] 暂未收到验证码，{check_interval}秒后重试...')
                time.sleep(check_interval)

            except Exception as e:
                self.logger.debug(f'获取异常: {e}')
                time.sleep(check_interval)

        elapsed = int(time.time() - start_time)
        self.logger.error(f'超时未收到验证码（{elapsed}秒）')
        return None

    def _is_verification_email(self, email_item: Dict) -> bool:
        """检查是否是验证邮件"""
        from_addr = email_item.get('from', '').lower()
        subject = email_item.get('subject', '').lower()
        content = (email_item.get('content', '') + email_item.get('htmlContent', '')).lower()

        # 检查发件人
        if 'firebase' in from_addr or 'warp' in from_addr or 'noreply' in from_addr or 'cursor' in from_addr:
            return True

        # 检查主题
        if any(keyword in subject for keyword in ['firebase', 'warp', 'verification', 'verify', 'code', 'cursor']):
            return True

        # 检查内容
        if any(keyword in content for keyword in ['firebase', 'warp', 'verification', 'verify', 'cursor']):
            return True

        return False

    def _extract_code(self, content: str) -> Optional[str]:
        """从邮件内容中提取验证码"""
        import re

        # 尝试多种模式提取6位数字验证码
        patterns = [
            r'verification code is[:\s]+([0-9]{6})',  # verification code is: 123456
            r'code[:\s]+([0-9]{6})',                   # code: 123456
            r'verify[:\s]+([0-9]{6})',                 # verify: 123456
            r'>([0-9]{6})<',                           # HTML标签中的数字
            r'\b([0-9]{6})\b',                         # 独立的6位数字
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                code = match.group(1)
                # 验证是否是纯数字
                if code.isdigit() and len(code) == 6:
                    return code

        return None

    def delete(self):
        """删除邮箱（GPTMail不支持删除）"""
        if self.email:
            self.logger.debug(f'[GPTMail] 邮箱无需删除: {self.email}')


class CursorAuto:
    """Cursor自动化 - 参考Factory.ai实现"""
    
    def __init__(self, logger: Logger, proxy: str = None):
        self.logger = logger
        
        # 生成随机浏览器指纹
        self.fingerprint = generate_random_fingerprint()
        self.logger.info('[指纹] 生成随机浏览器指纹（模拟真实用户）')
        self.logger.info(f'[指纹] Chrome版本: {self.fingerprint["chrome_version"]}')
        self.logger.info(f'[指纹] 平台: {self.fingerprint["platform"]}')
        self.logger.info(f'[指纹] 分辨率: {self.fingerprint["screen_resolution"]}')
        self.logger.info(f'[指纹] 语言: {self.fingerprint["accept_language"]}')
        self.logger.info(f'[指纹] 时区: UTC{self.fingerprint["timezone"]}')
        self.logger.info(f'[指纹] GPU: {self.fingerprint["webgl_vendor"]} / {self.fingerprint["webgl_renderer"][:40]}...')
        self.logger.info(f'[指纹] CPU核心: {self.fingerprint["hardware_concurrency"]} / 内存: {self.fingerprint["device_memory"]}GB')
        
        # 使用curl_cffi（如果可用）
        if HAS_CURL_CFFI:
            try:
                self.session = requests.Session(impersonate="chrome120")
                self.logger.info('[curl_cffi] 已初始化，模拟Chrome 120')
            except Exception as e:
                self.logger.warning(f'[curl_cffi] 初始化失败: {e}')
                self.logger.info('[fallback] 使用标准requests库')
                import requests as std_requests
                self.session = std_requests.Session()
        else:
            import requests as std_requests
            self.session = std_requests.Session()
        
        # 应用随机指纹到session
        self.session.headers.update({
            'User-Agent': self.fingerprint['user_agent'],
            'Accept-Language': self.fingerprint['accept_language'],
            'sec-ch-ua': f'"Chromium";v="{self.fingerprint["chrome_version"]}", "Google Chrome";v="{self.fingerprint["chrome_version"]}", "Not-A.Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': f'"{self.fingerprint["platform"]}"',
        })
        
        if proxy:
            self.proxies = {'http': proxy, 'https': proxy}
        else:
            self.proxies = None
        
        self.email = None
        self.session_token = None
        self.access_token = None
        self.refresh_token = None
        self.subscription_id = None
        self.authorization_session_id = None
        self.authentication_challenge_id = None
        self.phone_verification_triggered = False  # 是否触发手机验证
        
        # Cursor的配置
        self.client_id = 'client_01GS6W3C96KW4WRS6Z93JCE2RJ'
        self.redirect_uri = 'https://cursor.com/api/auth/callback'
        
        # 生成nonce并设置state
        self.nonce = str(uuid.uuid4())
        self.state = '%7B%22returnTo%22%3A%22https%3A//cursor.com/cn/dashboard%22%2C%22nonce%22%3A%22' + self.nonce + '%22%7D'
        
        # 设置必要的Cookies（cursor.com需要）
        self.session.cookies.set('generaltranslation.locale-routing-enabled', 'true', domain='.cursor.com')
        self.session.cookies.set('generaltranslation.referrer-locale', 'cn', domain='.cursor.com')
        self.session.cookies.set('WorkosCursorAuthNonce', self.nonce, domain='.cursor.com')
    
    def init_auth_session(self) -> bool:
        """初始化认证session"""
        self.logger.step(1, 4, '初始化OAuth认证')
        
        try:
            auth_url = (
                f"https://api.workos.com/user_management/authorize"
                f"?client_id={self.client_id}"
                f"&provider=authkit"
                f"&redirect_uri={self.redirect_uri}"
                f"&response_type=code"
                f"&state={self.state}"
            )
            
            self.logger.info(f'[请求] GET {auth_url[:100]}...')
            
            response = self.session.get(
                auth_url,
                proxies=self.proxies,
                allow_redirects=True,
                timeout=60,
                headers={'Referer': 'https://cursor.com/'}
            )
            
            self.logger.info(f'[响应] 状态: {response.status_code}')
            self.logger.info(f'[响应] 最终URL: {response.url[:100]}...')
            
            parsed = urlparse(response.url)
            params = parse_qs(parsed.query)
            
            if 'authorization_session_id' in params:
                self.authorization_session_id = params['authorization_session_id'][0]
                self.logger.success(f'Session ID: {self.authorization_session_id}')
                
                # 模拟用户思考时间
                self.logger.debug('[延迟] 模拟用户查看页面...')
                random_delay(1.5, 3.5)
                
                return True
            
            self.logger.error('未获取到Session ID')
            return False
                
        except Exception as e:
            self.logger.error(f'初始化失败: {e}')
            return False
    
    def submit_email(self, email: str) -> bool:
        """提交邮箱 - 使用Next.js Server Actions格式"""
        self.logger.step(2, 4, '提交邮箱，请求验证码')

        self.email = email

        try:
            submit_url = (
                f"https://authenticator.cursor.sh/"
                f"?client_id={self.client_id}"
                f"&redirect_uri={self.redirect_uri}"
                f"&state={self.state}"
                f"&authorization_session_id={self.authorization_session_id}"
            )

            self.logger.info(f'[请求] POST {submit_url[:100]}...')

            # 生成随机boundary
            boundary = f"----WebKitFormBoundary{''.join(random.choices(string.ascii_letters + string.digits, k=16))}"

            # 关键：使用Next.js Server Actions格式
            form_data = f"""------{boundary}\r
Content-Disposition: form-data; name="1_email"\r
\r
{email}\r
------{boundary}\r
Content-Disposition: form-data; name="1_redirect_uri"\r
\r
{self.redirect_uri}\r
------{boundary}\r
Content-Disposition: form-data; name="1_authorization_session_id"\r
\r
{self.authorization_session_id}\r
------{boundary}\r
Content-Disposition: form-data; name="1_state"\r
\r
{self.state}\r
------{boundary}\r
Content-Disposition: form-data; name="0"\r
\r
["$K1"]\r
------{boundary}--\r
"""

            response = self.session.post(
                submit_url,
                data=form_data,
                proxies=self.proxies,
                allow_redirects=False,
                timeout=30,  # ✅ 缩短超时时间：60秒 -> 30秒
                headers={
                    'Content-Type': f'multipart/form-data; boundary=----{boundary}',
                    'Referer': submit_url,
                    'Next-Action': 'c2e538693a70c633717214cacd5c6fdb8139f98d',  # 关键Header！
                    'Accept': 'text/x-component',  # 关键Header！
                }
            )

            self.logger.info(f'[响应] 状态码: {response.status_code}')

            # 模拟用户填写邮箱的时间
            self.logger.debug('[延迟] 模拟输入邮箱时间...')
            random_delay(0.8, 2.0)

            if response.status_code in [303, 302, 307]:
                redirect_url = response.headers.get('Location', '') or response.headers.get('x-action-redirect', '')
                self.logger.info(f'[重定向] {redirect_url[:100]}...')

                # ✅ 关键：检测radar-challenge，立即终止
                if 'radar-challenge' in redirect_url:
                    self.logger.warning('[检测] 提交邮箱后重定向到radar-challenge（手机验证）！立即终止')
                    self.phone_verification_triggered = True
                    return False

                # 检查重定向类型
                if redirect_url and '/password' in redirect_url:
                    # 重定向到password页面，但使用验证码登录（无需密码）
                    self.logger.info('[流程] 使用验证码登录（无需密码）')
                    
                    # 模拟查看页面
                    random_delay(1.0, 2.5)
                    
                    return self._submit_passwordless(redirect_url)
                    
                elif redirect_url and 'magic-code' in redirect_url:
                    # 已有账号，直接验证码登录
                    self.logger.info('[流程] 邮箱验证码登录')
                    
                    parsed = urlparse(redirect_url)
                    params = parse_qs(parsed.query)
                    
                    self.authentication_challenge_id = params.get('authentication_challenge_id', [None])[0]
                    
                    self.logger.success(f'验证码已发送! Challenge ID: {self.authentication_challenge_id}')
                    self.logger.info(f'邮箱: {email}')
                    
                    # 访问magic-code页面
                    full_url = f"https://authenticator.cursor.sh{redirect_url}" if redirect_url.startswith('/') else redirect_url
                    self.session.get(full_url, proxies=self.proxies, timeout=60)
                    
                    return True
                else:
                    self.logger.warning(f'未知重定向: {redirect_url}')
                    return False
            else:
                self.logger.warning(f'未预期的状态码: {response.status_code}')
                self.logger.info(f'响应内容: {response.text[:300]}')
                return False
                
        except Exception as e:
            self.logger.error(f'提交邮箱失败: {e}')
            return False
    
    def submit_verification_code(self, code: str) -> bool:
        """提交验证码"""
        self.logger.step(3, 4, '提交验证码')
        
        # 模拟用户输入验证码的时间
        self.logger.debug('[延迟] 模拟输入验证码...')
        random_delay(2.0, 4.0)
        
        try:
            submit_url = (
                f"https://authenticator.cursor.sh/magic-code"
                f"?authentication_challenge_id={self.authentication_challenge_id}"
                f"&state={self.state}"
                f"&redirect_uri={self.redirect_uri}"
                f"&authorization_session_id={self.authorization_session_id}"
            )
            
            self.logger.info(f'[请求] POST /magic-code')
            self.logger.info(f'[验证码] {code}')
            
            boundary = f"----WebKitFormBoundary{''.join(random.choices(string.ascii_letters + string.digits, k=16))}"
            
            # 使用Next.js Server Actions格式
            form_data = f"""------{boundary}\r
Content-Disposition: form-data; name="1_code"\r
\r
{code}\r
------{boundary}\r
Content-Disposition: form-data; name="1_redirect_uri"\r
\r
{self.redirect_uri}\r
------{boundary}\r
Content-Disposition: form-data; name="1_authorization_session_id"\r
\r
{self.authorization_session_id}\r
------{boundary}\r
Content-Disposition: form-data; name="1_state"\r
\r
{self.state}\r
------{boundary}\r
Content-Disposition: form-data; name="1_email"\r
\r
{self.email}\r
------{boundary}\r
Content-Disposition: form-data; name="1_authentication_challenge_id"\r
\r
{self.authentication_challenge_id}\r
------{boundary}\r
Content-Disposition: form-data; name="0"\r
\r
["$K1"]\r
------{boundary}--\r
"""
            
            response = self.session.post(
                submit_url,
                data=form_data,
                proxies=self.proxies,
                allow_redirects=False,
                timeout=30,  # ✅ 缩短超时时间：60秒 -> 30秒
                headers={
                    'Content-Type': f'multipart/form-data; boundary=----{boundary}',
                    'Referer': submit_url,
                    'Next-Action': '66aad60c4b11d5e466800de9726b3ad065b7d523',  # 关键Header！
                    'Accept': 'text/x-component',
                }
            )

            self.logger.info(f'[响应] 状态码: {response.status_code}')

            # ✅ 关键：检测 policy_denied 错误（域名被 Cursor 拉黑）
            try:
                response_text = response.text
                if 'policy_denied' in response_text or 'Authentication blocked' in response_text:
                    self.logger.error('[Policy Denied] 检测到域名被Cursor拉黑！')
                    self.logger.error(f'[错误信息] {response_text[:200]}')
                    self.logger.info('[处理] 将该邮箱域名加入黑名单')
                    self.phone_verification_triggered = True  # 使用相同的标记
                    return False
            except:
                pass
            
            # 处理重定向（关键修复：遇到callback或radar-challenge立即停止）
            redirect_count = 0
            oauth_code = None

            while response.status_code in [301, 302, 303, 307, 308] and redirect_count < 10:
                redirect_url = response.headers.get('Location') or response.headers.get('x-action-redirect')
                if not redirect_url:
                    break

                self.logger.info(f'[重定向{redirect_count+1}] {redirect_url[:100]}...')

                # ✅ 关键：检测radar-challenge，立即终止
                if 'radar-challenge' in redirect_url:
                    self.logger.warning('[检测] 重定向到radar-challenge（手机验证）！立即终止')
                    self.phone_verification_triggered = True
                    return False

                # 关键修复：如果重定向到callback，立即提取code并停止
                if 'cursor.com/api/auth/callback' in redirect_url and 'code=' in redirect_url:
                    self.logger.info('[检测] 重定向到OAuth callback，提取code')
                    parsed = urlparse(redirect_url)
                    params = parse_qs(parsed.query)
                    oauth_code = params.get('code', [None])[0]

                    if oauth_code:
                        self.logger.success(f'OAuth Code: {oauth_code}')
                        # 立即调用获取token，不再继续跟随重定向
                        return self._get_session_token(oauth_code)
                    else:
                        self.logger.error('callback URL中未找到code参数')
                        break

                if redirect_url.startswith('/'):
                    redirect_url = f"https://authenticator.cursor.sh{redirect_url}"

                response = self.session.get(redirect_url, proxies=self.proxies, allow_redirects=False, timeout=60)
                redirect_count += 1

                # ✅ 关键：访问后也检测URL
                if 'radar-challenge' in response.url:
                    self.logger.warning('[检测] 访问后URL包含radar-challenge！立即终止')
                    self.phone_verification_triggered = True
                    return False
            
            self.logger.info(f'[最终] URL: {response.url[:100]}...')
            
            # 检查是否成功回调到cursor.com（备用检查）
            if 'cursor.com/api/auth/callback' in response.url and not oauth_code:
                # 提取OAuth code
                parsed = urlparse(response.url)
                params = parse_qs(parsed.query)
                oauth_code = params.get('code', [None])[0]
                
                if oauth_code:
                    self.logger.success(f'OAuth Code: {oauth_code}')
                    
                    # 回调获取Session Token
                    return self._get_session_token(oauth_code)
                else:
                    self.logger.error('未获取到OAuth code')
                    return False
            
            elif 'radar-challenge' in response.url:
                # 触发了手机验证 - 标记特殊状态并立即返回
                self.logger.warning('[Radar Challenge] 检测到手机验证！立即终止')
                self.phone_verification_triggered = True
                return False  # 立即返回，不再继续
            
            elif 'cursor.com' in response.url:
                # 已经在cursor.com，可能已登录
                self.logger.success('已重定向到cursor.com')
                return self._check_login_status()
            
            else:
                self.logger.warning(f'未重定向到cursor.com: {response.url}')
                return False
                
        except Exception as e:
            self.logger.error(f'提交验证码失败: {e}')
            return False
    
    def _get_session_token(self, oauth_code: str) -> bool:
        """获取Session Token"""
        self.logger.step(4, 4, 'OAuth回调获取Token')
        
        try:
            callback_url = f'https://cursor.com/api/auth/callback?code={oauth_code}&state={self.state}'
            
            self.logger.info(f'[请求] GET /api/auth/callback')
            self.logger.debug(f'[Code] {oauth_code}')
            
            # 设置正确的Headers（模拟浏览器跳转）
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Referer': 'https://authenticator.cursor.sh/',
                'Sec-Fetch-Site': 'cross-site',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Dest': 'document',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = self.session.get(
                callback_url,
                proxies=self.proxies,
                allow_redirects=False,
                timeout=60,
                headers=headers
            )
            
            self.logger.info(f'[响应] 状态码: {response.status_code}')
            
            # 检查状态码（应该是302重定向）
            if response.status_code in [302, 303]:
                # 检查Set-Cookie
                if 'WorkosCursorSessionToken' in response.cookies:
                    self.session_token = response.cookies['WorkosCursorSessionToken']
                    self.logger.success(f'Session Token: {self.session_token[:50]}...')
                    
                    # URL解码Token（如果需要）
                    from urllib.parse import unquote
                    decoded_token = unquote(self.session_token)
                    if decoded_token != self.session_token:
                        self.logger.debug(f'[Token] URL解码: {decoded_token[:50]}...')
                        self.session_token = decoded_token
                    
                    # 解析token获取 user_id 和 JWT
                    # 格式: user_01XXX::eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
                    if '::' in self.session_token:
                        parts = self.session_token.split('::', 1)
                        user_id = parts[0]
                        jwt_token = parts[1] if len(parts) > 1 else None
                        
                        if jwt_token:
                            # 保存 access_token 和 refresh_token（都是同一个JWT）
                            self.access_token = jwt_token
                            self.refresh_token = jwt_token
                            
                            self.logger.debug(f'[解析] User ID: {user_id}')
                            self.logger.debug(f'[解析] Access Token: {jwt_token[:50]}...')
                    
                    # 设置cookie用于后续请求
                    self.session.cookies.set('WorkosCursorSessionToken', self.session_token, domain='.cursor.com')
                    
                    # 获取重定向位置
                    location = response.headers.get('Location', '')
                    if location:
                        self.logger.info(f'[重定向] {location[:80]}...')
                    
                    return True
                else:
                    self.logger.error('响应中未包含Session Token')
                    self.logger.debug(f'Cookies: {dict(response.cookies)}')
                    return False
            elif response.status_code == 500:
                self.logger.error('服务器错误 (500)')
                self.logger.debug(f'响应: {response.text[:200]}...')
                return False
            else:
                self.logger.warning(f'未预期的状态码: {response.status_code}')
                
                # 尝试从cookies中获取token
                if 'WorkosCursorSessionToken' in response.cookies:
                    self.session_token = response.cookies['WorkosCursorSessionToken']
                    self.logger.success(f'Session Token: {self.session_token[:50]}...')
                    
                    # URL解码Token
                    from urllib.parse import unquote
                    decoded_token = unquote(self.session_token)
                    if decoded_token != self.session_token:
                        self.logger.debug(f'[Token] URL解码: {decoded_token[:50]}...')
                        self.session_token = decoded_token
                    
                    # 解析token获取 user_id 和 JWT
                    if '::' in self.session_token:
                        parts = self.session_token.split('::', 1)
                        user_id = parts[0]
                        jwt_token = parts[1] if len(parts) > 1 else None
                        
                        if jwt_token:
                            self.access_token = jwt_token
                            self.refresh_token = jwt_token
                            self.logger.debug(f'[解析] User ID: {user_id}')
                    
                    self.session.cookies.set('WorkosCursorSessionToken', self.session_token, domain='.cursor.com')
                    return True
                else:
                    self.logger.error('未获取到Session Token')
                    return False
                
        except Exception as e:
            self.logger.error(f'获取Token失败: {e}')
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    def _submit_passwordless(self, password_redirect_url: str) -> bool:
        """提交验证码登录请求（无密码方式）"""
        self.logger.info('[验证码登录] POST /password (intent=magic-code)')
        
        try:
            # 构造完整URL
            full_url = f"https://authenticator.cursor.sh{password_redirect_url}" if password_redirect_url.startswith('/') else password_redirect_url
            
            # 先访问password页面
            self.logger.info(f'[1] 先访问/password页面')
            resp_page = self.session.get(full_url, proxies=self.proxies, timeout=60)
            self.logger.info(f'     页面加载: {resp_page.status_code}')
            
            # 模拟用户阅读页面
            random_delay(1.0, 2.5)
            
            # 从页面提取Turnstile site-key
            turnstile_sitekey = None
            
            # 尝试多种模式提取sitekey
            sitekey_patterns = [
                r'sitekey["\']?\s*[:=]\s*["\']([^"\']+)',
                r'data-sitekey["\']?\s*[:=]\s*["\']([^"\']+)',
                r'"siteKey":\s*"([^"]+)"',
                r'turnstile.*?sitekey.*?["\']([0-9a-zA-Z_-]+)',
            ]
            
            for pattern in sitekey_patterns:
                match = re.search(pattern, resp_page.text, re.IGNORECASE | re.DOTALL)
                if match:
                    turnstile_sitekey = match.group(1)
                    self.logger.info(f'     提取到Site-Key: {turnstile_sitekey}')
                    break
            
            if not turnstile_sitekey:
                # 保存页面供调试（已禁用，避免产生大量文件）
                # debug_page = f'debug_password_page_{int(time.time())}.html'
                # with open(debug_page, 'w', encoding='utf-8') as f:
                #     f.write(resp_page.text)
                self.logger.warning(f'     未找到sitekey')
            
            # 模拟用户准备提交
            random_delay(0.5, 1.5)
            
            self.logger.info(f'[2] POST /password')
            self.logger.info(f'     说明: password留空，intent=magic-code')
            self.logger.warning('')
            self.logger.warning('[Turnstile] 需要Cloudflare Turnstile验证！')
            self.logger.warning('')
            
            # 获取bot_detection_token
            bot_token = None

            if turnstile_sitekey and CAPTCHA_API_KEY:
                # 使用2captcha自动解决
                self.logger.info('[2captcha] 自动解决Turnstile...')
                bot_token = solve_turnstile_2captcha(turnstile_sitekey, full_url, CAPTCHA_API_KEY, self.logger)

            if not bot_token:
                # ✅ 检查是否在批量模式（通过检查 logger 类型）
                is_batch_mode = hasattr(self.logger, '__class__') and 'Silent' in self.logger.__class__.__name__

                if is_batch_mode:
                    # 批量模式：直接失败，不等待用户输入
                    self.logger.error('[Turnstile] 需要验证但未配置自动解决方案')
                    self.logger.error('[建议] 请在 config.ini 中配置 captcha_api_key')
                    self.logger.error('[说明] 批量模式下不支持手动输入，直接跳过')
                    return False
                else:
                    # 单线程模式：手动输入
                    print()
                    print('='*60)
                    print('需要Cloudflare Turnstile验证！')
                    print('='*60)
                    print()
                    print('步骤:')
                    print('  1. 用浏览器访问下面的URL')
                    print(f'  2. 完成Turnstile验证（勾选"我不是机器人"）')
                    print('  3. 按F12 → Network → 点击"继续"或"发送验证码"按钮')
                    print('  4. 找到POST /password请求 → Payload/Form Data')
                    print('  5. 复制 1_bot_detection_token 的值（很长的字符串）')
                    print()
                    print(f'URL: {full_url}')
                    print()
                    print('='*60)
                    print()

                    bot_token = input('请输入bot_detection_token: ').strip()

            if not bot_token:
                self.logger.error('[Token] 未获取到token，无法继续')
                return False
            
            self.logger.info(f'[Token] 长度: {len(bot_token)} 字符')
            
            # 关键：password留空，intent设为magic-code，添加bot_detection_token
            boundary = f"----WebKitFormBoundary{''.join(random.choices(string.ascii_letters + string.digits, k=16))}"
            
            form_data = f"""------{boundary}\r
Content-Disposition: form-data; name="1_bot_detection_token"\r
\r
{bot_token}\r
------{boundary}\r
Content-Disposition: form-data; name="1_email"\r
\r
{self.email}\r
------{boundary}\r
Content-Disposition: form-data; name="1_password"\r
\r
\r
------{boundary}\r
Content-Disposition: form-data; name="1_intent"\r
\r
magic-code\r
------{boundary}\r
Content-Disposition: form-data; name="1_redirect_uri"\r
\r
{self.redirect_uri}\r
------{boundary}\r
Content-Disposition: form-data; name="1_authorization_session_id"\r
\r
{self.authorization_session_id}\r
------{boundary}\r
Content-Disposition: form-data; name="1_state"\r
\r
{self.state}\r
------{boundary}\r
Content-Disposition: form-data; name="0"\r
\r
["$K1"]\r
------{boundary}--\r
"""
            
            response = self.session.post(
                full_url,
                data=form_data,
                proxies=self.proxies,
                allow_redirects=False,
                timeout=30,  # ✅ 缩短超时：60秒 -> 30秒
                headers={
                    'Content-Type': f'multipart/form-data; boundary=----{boundary}',
                    'Referer': full_url,
                    'Next-Action': '7eca8cdca87b1e904313af18fc0ac99b08c94b52',  # password页面的action
                    'Accept': 'text/x-component',
                }
            )

            self.logger.info(f'[响应] 状态码: {response.status_code}')
            self.logger.info(f'[响应] Content-Type: {response.headers.get("content-type", "")}')

            # 打印所有重定向相关的header
            for header_name in ['Location', 'x-action-redirect', 'x-action-revalidate']:
                value = response.headers.get(header_name, '')
                if value:
                    self.logger.info(f'[响应] {header_name}: {value[:100]}...')

            # 保存响应用于调试（已禁用，避免产生大量文件）
            # debug_file = f'debug_password_response_{int(time.time())}.txt'
            # with open(debug_file, 'w', encoding='utf-8') as f:
            #     f.write(f'Status: {response.status_code}\n')
            #     f.write(f'Headers:\n')
            #     for k, v in response.headers.items():
            #         f.write(f'  {k}: {v}\n')
            #     f.write(f'\nBody:\n')
            #     f.write(response.text)
            # self.logger.info(f'[调试] 响应已保存到: {debug_file}')

            if response.status_code in [303, 302, 307]:
                redirect_url = response.headers.get('Location', '') or response.headers.get('x-action-redirect', '')
                self.logger.info(f'[重定向] {redirect_url[:100]}...')

                # ✅ 关键：检测radar-challenge，立即终止
                if 'radar-challenge' in redirect_url:
                    self.logger.warning('[检测] password页面重定向到radar-challenge（手机验证）！立即终止')
                    self.phone_verification_triggered = True
                    return False

                if 'magic-code' in redirect_url:
                    # 解析参数
                    parsed = urlparse(redirect_url)
                    params = parse_qs(parsed.query)
                    
                    self.authentication_challenge_id = params.get('authentication_challenge_id', [None])[0]
                    
                    self.logger.success(f'验证码已发送！')
                    self.logger.success(f'Challenge ID: {self.authentication_challenge_id}')
                    self.logger.info(f'邮箱: {self.email}')
                    
                    # 访问magic-code页面
                    full_url = f"https://authenticator.cursor.sh{redirect_url}" if redirect_url.startswith('/') else redirect_url
                    self.session.get(full_url, proxies=self.proxies, timeout=60)
                    
                    return True
                else:
                    self.logger.warning('未重定向到magic-code')
                    return False
            elif response.status_code == 200:
                self.logger.error(f'返回200，未重定向')
                self.logger.error(f'Content-Type: {response.headers.get("content-type")}')
                self.logger.error(f'响应前500字符: {response.text[:500]}')
                return False
            else:
                self.logger.error(f'提交失败: {response.status_code}')
                return False
                
        except Exception as e:
            self.logger.error(f'提交异常: {e}')
            return False
    
    def _handle_phone_verification(self, pending_token: str, user_id: str) -> bool:
        """处理手机验证（使用SMS-Activate）"""
        self.logger.info('')
        self.logger.info('='*60)
        self.logger.info('[手机验证] 开始自动手机验证')
        self.logger.info('='*60)
        
        # 使用5sim API
        fivesim_api_key = 'eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTIzMzc5NjcsImlhdCI6MTc2MDgwMTk2NywicmF5IjoiZjZiY2ExOWEzMTIwZWNkYzdmNDI0NTM3YzUyNDI1ODkiLCJzdWIiOjM1NDgwOTh9.26NxQ67w51LYf59WqfvCq47jmPZM_JpUrYmISO4-e_IHrSdqYZPLhabi6cJPi9841HbC_yxngR7pWxFIauoVqmUs83eQf-ZCUFau8eSRcrAI5U5IlsTPW5xATyAJHyv2HkuCZcv2EtyXMlpbCifQUal13RE6b5ErcpzfZnOT8eqMjqQSU6M9RaJS8hl2I0RWMmoL6oe988CGFYF05p57IWBXTYIWbvPBt6XhwtoBA4ykYX5KN5AvlFMGfnMrJ3O7G1UHOInfWVe6sein1lb6ZisL9XULDY1qQRzeIPXZwgfigbJGdQYNeLExOw9-MBYP8r9HBHzw_BVlWiNsH3fu-g'
        
        try:
            # 1. 获取手机号（使用5sim）
            sms_data = get_5sim_number(fivesim_api_key, 'other', self.logger)
            
            if not sms_data:
                self.logger.error('[手机验证] 获取号码失败')
                return False
            
            phone = sms_data['phone']
            activation_id = sms_data['id']  # 5sim使用'id'而不是'activation_id'
            
            # 模拟用户查看手机号
            self.logger.debug('[延迟] 模拟用户准备输入手机号...')
            random_delay(1.5, 3.0)
            
            # 2. 提交手机号到Cursor
            self.logger.info('[手机验证] 提交手机号到Cursor')
            
            send_url = (
                f"https://authenticator.cursor.sh/radar-challenge/send"
                f"?pending_authentication_token={pending_token}"
                f"&user_id={user_id}"
                f"&state={self.state}"
                f"&redirect_uri={self.redirect_uri}"
                f"&authorization_session_id={self.authorization_session_id}"
            )
            
            # 先GET访问页面
            self.logger.info('[1] GET访问/radar-challenge/send页面')
            self.logger.info(f'[URL] {send_url[:100]}...')
            
            resp_page = self.session.get(send_url, proxies=self.proxies, timeout=60)
            self.logger.info(f'     页面状态: {resp_page.status_code}')
            self.logger.debug(f'     Cookies: {dict(resp_page.cookies)}')
            
            # 保存页面HTML供分析
            page_file = f'debug_radar_send_page_{int(time.time())}.html'
            with open(page_file, 'w', encoding='utf-8') as f:
                f.write(resp_page.text)
            self.logger.info(f'     页面已保存: {page_file}')
            
            # 从页面提取Next-Action（使用多种模式）
            import re
            next_action = None
            
            # 尝试多种模式
            patterns = [
                r'"next-action"\s*:\s*"([^"]+)"',
                r'next-action["\']?\s*[:=]\s*["\']([^"\']+)',
                r'action["\']:\s*["\']([a-f0-9]{40})',
                r'([a-f0-9]{40})',  # 最后尝试找40位十六进制
            ]
            
            for pattern in patterns:
                match = re.search(pattern, resp_page.text, re.IGNORECASE)
                if match:
                    next_action = match.group(1)
                    self.logger.info(f'     提取Next-Action: {next_action} (模式: {pattern[:30]}...)')
                    break
            
            if not next_action:
                # 使用HAR中radar-challenge/send的Next-Action
                next_action = '8e7a636b3b401634f6a5edf8d0dc7257716997ab'
                self.logger.warning(f'     未提取到Next-Action，使用HAR中的值')
                self.logger.warning(f'     请检查 {page_file} 查找正确的action值')
            
            # 模拟用户查看页面后准备操作
            random_delay(0.5, 1.5)
            
            # 解析手机号为国家码和本地号码
            self.logger.info('[2] 解析手机号格式')
            self.logger.info(f'     原始号码: {phone}')
            
            if phone.startswith('+'):
                # 移除+号后分析
                phone_digits = phone[1:]
                
                # 尝试识别国家码长度（1-3位）
                # 简单策略：前1-3位是国家码
                if phone_digits.startswith('1'):  # 美国/加拿大
                    country_code = '+1'
                    local_number = phone_digits[1:]
                elif phone_digits.startswith('44'):  # 英国
                    country_code = '+44'
                    local_number = phone_digits[2:]
                elif phone_digits.startswith('48'):  # 波兰
                    country_code = '+48'
                    local_number = phone_digits[2:]
                elif phone_digits.startswith('7'):  # 俄罗斯/哈萨克斯坦
                    country_code = '+7'
                    local_number = phone_digits[1:]
                elif phone_digits.startswith('86'):  # 中国
                    country_code = '+86'
                    local_number = phone_digits[2:]
                else:
                    # 默认前2位是国家码
                    country_code = f'+{phone_digits[:2]}'
                    local_number = phone_digits[2:]
            else:
                # 没有+号，假设前2位是国家码
                country_code = f'+{phone[:2]}'
                local_number = phone[2:]
            
            # 格式化local_number为 (XXX)XXX-XXXX 格式
            # 示例：530581134 -> (530)581-134
            if len(local_number) >= 6:
                # 格式化：前3位+括号，中3位，横线，剩余
                if len(local_number) == 9:
                    formatted_local = f'({local_number[:3]}){local_number[3:6]}-{local_number[6:]}'
                elif len(local_number) == 10:
                    formatted_local = f'({local_number[:3]}){local_number[3:6]}-{local_number[6:]}'
                else:
                    # 其他长度，简单格式化
                    mid = len(local_number) // 2
                    formatted_local = f'({local_number[:3]}){local_number[3:mid]}-{local_number[mid:]}'
            else:
                formatted_local = local_number
            
            self.logger.info(f'     国家码: {country_code}')
            self.logger.info(f'     本地号码: {local_number}')
            self.logger.info(f'     格式化本地号码: {formatted_local}')
            self.logger.info(f'     完整号码: {phone}')
            
            self.logger.info('[3] POST提交手机号')
            
            # 注意boundary格式：不带横线的随机字符串
            boundary = f"WebKitFormBoundary{''.join(random.choices(string.ascii_letters + string.digits, k=16))}"
            
            # 注意：state需要保持原始编码格式
            state_value = self.state if '%' in self.state else quote(self.state)
            
            # 数据中用6个横线
            form_data = f"""------{boundary}\r
Content-Disposition: form-data; name="1_country_code"\r
\r
{country_code}\r
------{boundary}\r
Content-Disposition: form-data; name="1_local_number"\r
\r
{formatted_local}\r
------{boundary}\r
Content-Disposition: form-data; name="1_phone_number"\r
\r
{phone}\r
------{boundary}\r
Content-Disposition: form-data; name="1_redirect_uri"\r
\r
{self.redirect_uri}\r
------{boundary}\r
Content-Disposition: form-data; name="1_authorization_session_id"\r
\r
{self.authorization_session_id}\r
------{boundary}\r
Content-Disposition: form-data; name="1_state"\r
\r
{state_value}\r
------{boundary}\r
Content-Disposition: form-data; name="1_user_id"\r
\r
{user_id}\r
------{boundary}\r
Content-Disposition: form-data; name="1_pending_authentication_token"\r
\r
{pending_token}\r
------{boundary}\r
Content-Disposition: form-data; name="0"\r
\r
["$K1"]\r
------{boundary}--\r
"""
            
            self.logger.debug(f'[表单数据]')
            self.logger.debug(f'  1_country_code: {country_code}')
            self.logger.debug(f'  1_local_number: {formatted_local}')  # 使用格式化的
            self.logger.debug(f'  1_phone_number: {phone}')
            self.logger.debug(f'  1_state: {state_value[:50]}...')
            self.logger.debug(f'  1_user_id: {user_id}')
            self.logger.debug(f'  1_pending_authentication_token: {pending_token[:30]}...')
            
            # Content-Type中boundary前有4个横线
            post_headers = {
                'Content-Type': f'multipart/form-data; boundary=----{boundary}',
                'Referer': send_url,
                'Next-Action': next_action,
                'Accept': 'text/x-component',
                'Origin': 'https://authenticator.cursor.sh',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Dest': 'empty'
            }
            
            self.logger.info(f'[请求] POST {send_url[:80]}...')
            self.logger.debug(f'[Headers] Next-Action: {next_action}')
            
            resp = self.session.post(
                send_url,
                data=form_data,
                proxies=self.proxies,
                allow_redirects=False,
                timeout=60,
                headers=post_headers
            )
            
            self.logger.info(f'[响应] 状态码: {resp.status_code}')
            self.logger.info(f'[响应] Body: {resp.text[:500]}')
            
            # 保存调试文件（已禁用，避免产生大量文件）
            # debug_file = f'debug_phone_send_{int(time.time())}.txt'
            # with open(debug_file, 'w', encoding='utf-8') as f:
            #     f.write(f'Status: {resp.status_code}\nHeaders:\n')
            #     for k, v in resp.headers.items():
            #         f.write(f'  {k}: {v}\n')
            #     f.write(f'\nBody:\n{resp.text}')
            # self.logger.info(f'[调试] 已保存: {debug_file}')
            
            # *** 关键：从响应体中提取verification_id ***
            verification_id = None
            try:
                # 从响应体的JSON数据中提取verification_id
                import re
                match = re.search(r'"verification_id"\s*:\s*"([^"]+)"', resp.text)
                if match:
                    verification_id = match.group(1)
                    self.logger.success(f'[提取] Verification ID: {verification_id}')
                else:
                    self.logger.warning('[警告] 未在响应中找到verification_id')
                    
                    # 尝试从Location header提取（备用方法）
                    location = resp.headers.get('Location', '') or resp.headers.get('x-action-redirect', '')
                    if 'verification_id=' in location:
                        parsed = urlparse(location)
                        params = parse_qs(parsed.query)
                        verification_id = params.get('verification_id', [None])[0]
                        if verification_id:
                            self.logger.info(f'[备用方法] 从URL提取: {verification_id}')
            except Exception as e:
                self.logger.warning(f'[提取] 提取verification_id失败: {e}')
            
            # 允许200/303状态码（Next.js可能返回200或303）
            if resp.status_code == 200:
                # 检查是否有明确的错误信息
                if '"error"' in resp.text.lower() and 'invalid' in resp.text.lower():
                    self.logger.error(f'手机号被拒绝: {resp.text[:200]}')
                    cancel_5sim_order(fivesim_api_key, activation_id)
                    return False
                
                self.logger.warning('[200] Next.js返回200，短信可能已发送')
                self.logger.info('[尝试] 继续等待短信...')
            elif resp.status_code not in [303, 302, 307]:
                self.logger.error(f'提交手机号失败: {resp.status_code}')
                self.logger.info('[尝试] 尽管状态码异常，仍尝试获取短信...')
            
            # 等待短信发送
            self.logger.debug('[延迟] 等待短信发送...')
            random_delay(1.5, 3.0)
            
            # 3. 获取短信验证码（使用5sim）
            self.logger.info('[SMS] 开始等待短信...')
            sms_code = get_5sim_code(fivesim_api_key, activation_id, self.logger, timeout=300)
            
            if not sms_code:
                self.logger.error('[手机验证] 未收到短信')
                cancel_5sim_order(fivesim_api_key, activation_id)
                return False
            
            # 模拟用户输入短信验证码
            self.logger.debug('[延迟] 模拟用户输入短信验证码...')
            random_delay(2.0, 4.0)
            
            # 4. 提交短信验证码
            self.logger.info('[手机验证] 提交短信验证码')
            self.logger.info(f'[验证码] {sms_code}')
            
            verify_url = (
                f"https://authenticator.cursor.sh/radar-challenge/verify"
                f"?authorization_session_id={self.authorization_session_id}"
                f"&redirect_uri={self.redirect_uri}"
                f"&state={self.state}"
            )
            
            # boundary格式：不带横线
            boundary = f"WebKitFormBoundary{''.join(random.choices(string.ascii_letters + string.digits, k=16))}"
            
            # state需要保持编码格式
            state_value = self.state if '%' in self.state else quote(self.state)
            
            # 构造multipart/form-data（注意：不能在parts之间添加额外换行）
            form_data = f"""------{boundary}\r
Content-Disposition: form-data; name="1_code"\r
\r
{sms_code}\r
------{boundary}\r
Content-Disposition: form-data; name="1_redirect_uri"\r
\r
{self.redirect_uri}\r
------{boundary}\r
Content-Disposition: form-data; name="1_authorization_session_id"\r
\r
{self.authorization_session_id}\r
------{boundary}\r
Content-Disposition: form-data; name="1_state"\r
\r
{state_value}\r
------{boundary}\r
Content-Disposition: form-data; name="1_pending_authentication_token"\r
\r
{pending_token}\r
------{boundary}\r
Content-Disposition: form-data; name="1_verification_id"\r
\r
{verification_id if verification_id else ""}\r
------{boundary}\r
Content-Disposition: form-data; name="1_phone_number"\r
\r
{phone}\r
------{boundary}\r
Content-Disposition: form-data; name="0"\r
\r
["$K1"]\r
------{boundary}--\r
"""
            
            if verification_id:
                self.logger.debug(f'[字段] verification_id: {verification_id}')
            else:
                self.logger.warning('[警告] verification_id为空')
            
            # 使用HAR中verify的Next-Action值（第400个请求）
            # 注意：这个值可能会变化，如果verify失败，尝试从页面提取
            verify_next_action = '5cded633b2181dd83758af9fe6a13b9e2b16ff50'
            
            self.logger.info(f'[请求] POST /radar-challenge/verify')
            self.logger.debug(f'[Next-Action] {verify_next_action}')
            if not verification_id:
                self.logger.warning('[警告] 没有verification_id，可能导致验证失败')
            else:
                self.logger.info(f'[字段] verification_id: {verification_id}')
            
            # Content-Type中4个横线
            resp = self.session.post(
                verify_url,
                data=form_data,
                proxies=self.proxies,
                allow_redirects=False,  # 关键修复：不自动重定向
                timeout=60,
                headers={
                    'Content-Type': f'multipart/form-data; boundary=----{boundary}',
                    'Referer': verify_url,
                    'Next-Action': verify_next_action,
                    'Accept': 'text/x-component',
                    'Origin': 'https://authenticator.cursor.sh',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Dest': 'empty'
                }
            )
            
            self.logger.info(f'[响应] 状态码: {resp.status_code}')
            
            # 处理重定向（手动跟随）
            if resp.status_code in [302, 303, 307, 308]:
                redirect_url = resp.headers.get('Location') or resp.headers.get('x-action-redirect')
                if redirect_url:
                    self.logger.info(f'[重定向] {redirect_url[:100]}...')
                    
                    # 关键：如果重定向到callback，直接提取code
                    if 'cursor.com/api/auth/callback' in redirect_url and 'code=' in redirect_url:
                        self.logger.success('[检测] 重定向到OAuth callback')
                        parsed = urlparse(redirect_url)
                        params = parse_qs(parsed.query)
                        oauth_code = params.get('code', [None])[0]
                        
                        if oauth_code:
                            self.logger.success(f'[手机验证成功] OAuth Code: {oauth_code}')
                            return self._get_session_token(oauth_code)
                    
                    # 否则跟随重定向
                    resp = self.session.get(redirect_url, proxies=self.proxies, allow_redirects=True, timeout=60)
                    self.logger.info(f'[最终] URL: {resp.url[:100]}...')
            
            # 检查最终URL
            if 'cursor.com/api/auth/callback' in resp.url:
                # 提取OAuth code
                parsed = urlparse(resp.url)
                params = parse_qs(parsed.query)
                oauth_code = params.get('code', [None])[0]
                
                if oauth_code:
                    self.logger.success(f'[手机验证成功] OAuth Code: {oauth_code}')
                    return self._get_session_token(oauth_code)
            
            elif 'cursor.com' in resp.url or 'WorkosCursorSessionToken' in self.session.cookies:
                # 已在cursor.com或有token
                if 'WorkosCursorSessionToken' in self.session.cookies:
                    self.session_token = self.session.cookies['WorkosCursorSessionToken']
                    self.logger.success(f'[手机验证成功] Session Token获取')
                    return True
                
                return self._check_login_status()
            
            else:
                self.logger.warning(f'[手机验证] 未重定向到cursor.com: {resp.url}')
                return False
                
        except Exception as e:
            self.logger.error(f'[手机验证] 异常: {e}')
            return False
    
    def _check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            resp = self.session.get('https://cursor.com/api/auth/me', proxies=self.proxies, timeout=30)
            if resp.status_code == 200:
                self.logger.success('已登录')
                return True
            return False
        except:
            return False
    
    def _verify_subscription(self) -> bool:
        """验证订阅状态"""
        self.logger.info('[验证] 检查订阅状态...')
        
        try:
            # 等待webhook处理
            self.logger.info('[等待] Stripe webhook处理中...')
            time.sleep(5)
            
            # 方法1: 检查 /api/auth/me
            resp = self.session.get('https://cursor.com/api/auth/me', proxies=self.proxies, timeout=30)
            
            if resp.status_code == 200:
                user_info = resp.json()
                subscription = user_info.get('subscription', {})
                
                if subscription and subscription.get('status') in ['active', 'trialing']:
                    self.logger.success('Pro订阅已激活！')
                    self.logger.info(f'订阅状态: {subscription.get("status", "N/A")}')
                    self.logger.info(f'订阅类型: {subscription.get("plan", "N/A")}')
                    self.logger.info(f'计费周期: {subscription.get("interval", "N/A")}')
                    
                    period_end = subscription.get('current_period_end')
                    if period_end:
                        self.logger.info(f'到期时间: {period_end}')
                    
                    return True
            
            # 方法2: 检查 /api/dashboard/list-invoices
            self.logger.info('[验证] 检查发票列表...')
            
            resp = self.session.get('https://cursor.com/api/dashboard/list-invoices', proxies=self.proxies, timeout=30)
            
            if resp.status_code == 200:
                invoices = resp.json()
                self.logger.debug(f'发票数据: {invoices}')
                
                if invoices:
                    self.logger.success('检测到订阅记录！')
                    
                    # 显示最新发票信息
                    if isinstance(invoices, list) and len(invoices) > 0:
                        latest = invoices[0]
                        self.logger.info(f'最新发票: {latest.get("id", "N/A")}')
                        self.logger.info(f'状态: {latest.get("status", "N/A")}')
                        self.logger.info(f'金额: ${latest.get("amount_paid", 0) / 100}')
                    
                    return True
            
            self.logger.warning('未检测到活跃订阅')
            self.logger.info('建议: 访问 https://cursor.com/dashboard 查看订阅状态')
            return False
                
        except Exception as e:
            self.logger.error(f'验证订阅失败: {e}')
            return False
    
    

    def _poll_payment_state(self, session_id: str, timeout: int = 30) -> bool:
        """轮询支付状态（从processing到succeeded）"""
        self.logger.info('[Poll] 轮询支付状态...')
        
        stripe_key = getattr(self, '_current_stripe_key', None)
        if not stripe_key:
            self.logger.error('[Poll] 缺少Stripe公钥')
            return False
        
        poll_url = f'https://api.stripe.com/v1/payment_pages/{session_id}/poll?key={stripe_key}'
        
        poll_headers = {
            'Origin': 'https://checkout.stripe.com',
            'Referer': 'https://checkout.stripe.com/',
            'User-Agent': self.fingerprint['user_agent']
        }
        
        start_time = time.time()
        attempt = 0
        
        while time.time() - start_time < timeout:
            attempt += 1
            
            try:
                resp = self.session.get(
                    poll_url,
                    headers=poll_headers,
                    proxies=self.proxies,
                    timeout=10
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    state = data.get('state')
                    
                    self.logger.debug(f'[Poll {attempt}] state={state}')
                    
                    # 检查是否有重定向URL（Stripe会在poll中返回）
                    redirect_url = data.get('redirect_to_url') or data.get('redirect_url')
                    if redirect_url:
                        self.logger.info(f'[Poll] 检测到重定向URL: {redirect_url[:80]}...')
                        
                        # 保存跳转URL供后续使用
                        self._stripe_redirect_url = redirect_url
                    
                    # 试用订阅：state=active 就是成功
                    # 付费订阅：state=succeeded 才是成功
                    if state in ['succeeded', 'active', 'complete']:
                        elapsed = int(time.time() - start_time)
                        self.logger.success(f'[Poll] 支付状态完成！state={state}, 耗时 {elapsed}秒')
                        return True
                    elif state in ['processing_subscription', 'processing']:
                        self.logger.debug(f'[Poll] 处理中...（尝试{attempt}次）')
                    else:
                        self.logger.warning(f'[Poll] 未知状态: {state}')
                else:
                    self.logger.debug(f'[Poll] 状态码: {resp.status_code}')
                    
            except Exception as e:
                self.logger.debug(f'[Poll] 异常: {e}')
            
            time.sleep(2)  # 每2秒轮询一次
        
        self.logger.warning(f'[Poll] 超时（{timeout}秒）')
        return False

    def _wait_for_webhook_completion(self, session_id: str, timeout: int = 60) -> bool:
        """等待Stripe webhook处理完成"""
        self.logger.info('[Webhook] 开始轮询...')
        
        # 关键修复：添加key参数和正确的headers
        stripe_key = getattr(self, '_current_stripe_key', None)
        if not stripe_key:
            self.logger.error('[Webhook] 缺少Stripe公钥')
            return False
        
        webhook_url = f'https://api.stripe.com/v1/checkout/sessions/completed_webhook_delivered/{session_id}?key={stripe_key}'
        
        webhook_headers = {
            'Origin': 'https://checkout.stripe.com',
            'Referer': 'https://checkout.stripe.com/',
            'User-Agent': self.fingerprint['user_agent']
        }
        
        start_time = time.time()
        attempt = 0
        
        while time.time() - start_time < timeout:
            attempt += 1
            
            try:
                resp = self.session.get(
                    webhook_url,
                    headers=webhook_headers,
                    proxies=self.proxies,
                    timeout=10
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    completed = data.get('completed', False)
                    
                    if completed:
                        elapsed = int(time.time() - start_time)
                        self.logger.success(f'[Webhook] 完成！耗时 {elapsed}秒（尝试{attempt}次）')
                        return True
                    else:
                        self.logger.debug(f'[Webhook] 等待中...（尝试{attempt}/{timeout}秒）')
                else:
                    self.logger.debug(f'[Webhook] 状态码: {resp.status_code}')
                
            except Exception as e:
                self.logger.debug(f'[Webhook] 异常: {e}')
            
            time.sleep(1)
        
        self.logger.warning(f'[Webhook] 超时（{timeout}秒），尝试了{attempt}次')
        return False
    
    def _confirm_activation_on_dashboard(self) -> bool:
        """访问dashboard确认激活"""
        try:
            self.logger.info('[Dashboard] 访问确认激活...')
            
            resp = self.session.get(
                'https://cursor.com/dashboard',
                proxies=self.proxies,
                allow_redirects=True,
                timeout=30
            )
            
            if resp.status_code == 200:
                self.logger.success('[Dashboard] 访问成功')
                return True
            else:
                self.logger.warning(f'[Dashboard] 状态码: {resp.status_code}')
                return False
                
        except Exception as e:
            self.logger.error(f'[Dashboard] 访问失败: {e}')
            return False
    
    def _acknowledge_privacy_and_disclaimer(self) -> bool:
        """确认隐私政策和免责声明 - 可选步骤（403时跳过）"""
        self.logger.info('[隐私] 同意隐私政策和免责声明...')
        
        try:
            # 1. 获取隐私模式设置
            self.logger.debug('[API 1/2] POST /api/dashboard/get-user-privacy-mode')
            resp1 = self.session.post(
                'https://cursor.com/api/dashboard/get-user-privacy-mode',
                json={},
                proxies=self.proxies,
                timeout=30
            )
            if resp1.status_code == 200:
                self.logger.success('[OK] get-user-privacy-mode')
                try:
                    privacy_data = resp1.json()
                    self.logger.debug(f'[隐私设置] {privacy_data}')
                except:
                    pass
            elif resp1.status_code == 403:
                self.logger.info('[跳过] get-user-privacy-mode返回403（订阅未激活或不需要）')
                return True  # 403不算失败，返回True继续
            else:
                self.logger.warning(f'[Warning] get-user-privacy-mode返回{resp1.status_code}')
            
            time.sleep(0.5)
            
            # 2. 确认宽限期免责声明（可选）
            self.logger.info('[API 2/2] POST /api/dashboard/web-acknowledge-grace-period-disclaimer')
            resp2 = self.session.post(
                'https://cursor.com/api/dashboard/web-acknowledge-grace-period-disclaimer',
                json={},
                proxies=self.proxies,
                timeout=30
            )
            if resp2.status_code == 200:
                self.logger.success('[OK] ✓ 已同意隐私政策和条款')
                return True
            elif resp2.status_code == 403:
                self.logger.info('[跳过] web-acknowledge-grace-period-disclaimer返回403（订阅未激活或不需要）')
                return True  # 403不算失败，返回True继续
            else:
                self.logger.warning(f'[Warning] web-acknowledge-grace-period-disclaimer返回{resp2.status_code}')
                return True  # 不阻塞后续流程
                
        except Exception as e:
            self.logger.warning(f'[隐私] 异常: {e}（不影响订阅激活）')
            return True  # 异常也不阻塞
    
    def _sync_subscription_status(self) -> bool:
        """同步订阅状态 - 关键步骤！模拟浏览器调用Cursor API"""
        self.logger.info('[同步] 调用Cursor API同步订阅状态...')
        
        try:
            # 1. 调用 /api/dashboard/get-me
            self.logger.debug('[API 1/5] POST /api/dashboard/get-me')
            resp1 = self.session.post(
                'https://cursor.com/api/dashboard/get-me',
                proxies=self.proxies,
                timeout=30
            )
            if resp1.status_code == 200:
                self.logger.debug('[OK] get-me')
            
            # 短暂延迟，模拟浏览器行为
            time.sleep(0.5)
            
            # 2. 调用 /api/auth/me（基本信息）
            self.logger.debug('[API 2/5] GET /api/auth/me')
            resp2 = self.session.get(
                'https://cursor.com/api/auth/me',
                proxies=self.proxies,
                timeout=30
            )
            if resp2.status_code == 200:
                self.logger.debug('[OK] auth/me')
            
            time.sleep(0.5)
            
            # 3. 调用隐私政策确认（可选，403时自动跳过）
            self.logger.info('[API 3/5] 确认隐私政策和条款...')
            privacy_ok = self._acknowledge_privacy_and_disclaimer()
            if privacy_ok:
                self.logger.debug('[隐私] 已处理')
            else:
                self.logger.debug('[隐私] 跳过')
            
            time.sleep(0.5)
            
            # 4. 调用 /api/usage-summary（关键！这里有订阅信息）
            self.logger.info('[API 4/5] GET /api/usage-summary')
            resp3 = self.session.get(
                'https://cursor.com/api/usage-summary',
                proxies=self.proxies,
                timeout=30
            )
            if resp3.status_code == 200:
                try:
                    usage_data = resp3.json()
                    self.logger.success('[OK] usage-summary 成功')
                    
                    # 检查订阅状态
                    membership_type = usage_data.get('membershipType')
                    if membership_type:
                        self.logger.success(f'[发现] membershipType: {membership_type}')
                        
                        if membership_type in ['free_trial', 'pro', 'business']:
                            self.logger.success('[确认] Pro订阅已激活！')
                            
                            # 显示详细信息
                            if 'billingCycleStart' in usage_data:
                                self.logger.info(f'计费周期开始: {usage_data["billingCycleStart"]}')
                            if 'billingCycleEnd' in usage_data:
                                self.logger.info(f'计费周期结束: {usage_data["billingCycleEnd"]}')
                            
                            return True
                        else:
                            self.logger.warning(f'[未知] membershipType: {membership_type}')
                    else:
                        self.logger.warning('[未发现] membershipType 字段')
                        self.logger.debug(f'响应: {json.dumps(usage_data, indent=2)[:300]}')
                except Exception as e:
                    self.logger.debug(f'解析usage-summary失败: {e}')
            else:
                self.logger.warning(f'[Warning] usage-summary返回{resp3.status_code}')
            
            time.sleep(0.5)
            
            # 5. 调用 /api/usage（额外信息）
            self.logger.debug('[API 5/5] GET /api/usage')
            resp4 = self.session.get(
                'https://cursor.com/api/usage',
                proxies=self.proxies,
                timeout=30
            )
            if resp4.status_code == 200:
                self.logger.debug('[OK] usage')
            
            return False  # 未找到订阅信息
            
        except Exception as e:
            self.logger.error(f'[同步] 失败: {e}')
            return False
    
    def generate_subscription_link(self) -> Optional[str]:
        """生成订阅链接（不自动支付）"""
        self.logger.info('')
        self.logger.info('='*60)
        self.logger.info('[订阅链接] 生成订阅链接')
        self.logger.info('='*60)
        
        try:
            # 获取Stripe配置
            self.logger.info('[1/2] 获取Stripe配置')
            
            resp = self.session.get('https://cursor.com/api/auth/stripe', proxies=self.proxies, timeout=30)
            
            if resp.status_code != 200:
                self.logger.error(f'获取失败: HTTP {resp.status_code}')
                return None
            
            stripe_data = resp.json()
            stripe_key = stripe_data.get('publishable_key')
            
            if not stripe_key:
                stripe_key = 'pk_live_51Lb5LzB4TZWxSIGU4LcaRyvT5xW1Iw8Z3E1iOpuCblBLoLhoq3xQnt2U6sR0kfr6wwTdLdQCykfzNnw778PaO7n200tsRmVe72'
                self.logger.info('[Fallback] 使用默认Stripe公钥')
            
            self.logger.success(f'Stripe公钥: {stripe_key[:50]}...')
            
            # 创建Checkout Session
            self.logger.info('[2/2] 创建Checkout Session')
            self.logger.info('[模式] 7天免费试用')
            
            resp = self.session.post(
                'https://cursor.com/api/checkout',
                json={
                    'tier': PLAN,
                    'allowTrial': True,
                    'allowAutomaticPayment': False
                },
                proxies=self.proxies,
                timeout=30
            )
            
            if resp.status_code != 200:
                self.logger.error(f'创建失败: {resp.status_code}')
                return None
            
            checkout_url = resp.json()
            session_id = checkout_url.split('/pay/')[1].split('#')[0]
            
            self.logger.success('='*60)
            self.logger.success('订阅链接生成成功！')
            self.logger.success('='*60)
            self.logger.info(f'Session ID: {session_id}')
            self.logger.info(f'订阅链接: {checkout_url}')
            self.logger.info('')
            self.logger.info('[提示] 请在浏览器中打开此链接完成支付')
            self.logger.info('[提示] 链接已保存到 cursor-2-cookies.txt')
            
            return checkout_url
            
        except Exception as e:
            self.logger.error(f'生成订阅链接失败: {e}')
            import traceback
            self.logger.debug(traceback.format_exc())
            return None
    
    def activate_pro(self, card_info: Dict, billing_details: Dict) -> bool:
        """激活Pro服务"""
        
        self.logger.info('')
        self.logger.info('='*60)
        self.logger.info('[Pro] 开始激活')
        self.logger.info('='*60)
        
        try:
            # 先访问trial页面，初始化用户状态
            self.logger.info('[准备] 访问试用页面，初始化状态...')
            
            try:
                # 访问/trial会重定向到/cn/trial（根据locale）
                trial_resp = self.session.get('https://cursor.com/trial', proxies=self.proxies, timeout=30, allow_redirects=True)
                self.logger.debug(f'[Trial] 状态码: {trial_resp.status_code}')
                self.logger.debug(f'[Trial] 最终URL: {trial_resp.url[:100]}...')
                
                if trial_resp.status_code == 200:
                    self.logger.success('试用页面加载成功')
                else:
                    self.logger.warning(f'试用页面状态异常: {trial_resp.status_code}')
            except Exception as e:
                self.logger.warning(f'访问试用页面异常: {e}')
            
            # 先检查用户信息和状态
            self.logger.info('[检查] 获取用户信息')
            
            try:
                me_resp = self.session.get('https://cursor.com/api/auth/me', proxies=self.proxies, timeout=30)
                self.logger.debug(f'[/api/auth/me] 状态码: {me_resp.status_code}')
                
                if me_resp.status_code == 200:
                    user_info = me_resp.json()
                    self.logger.debug(f'[用户] ID: {user_info.get("id", "N/A")}')
                    self.logger.debug(f'[用户] Email: {user_info.get("email", "N/A")}')
                    self.logger.debug(f'[用户] 订阅状态: {user_info.get("subscription", {})}')
                    
                    # 检查是否已有订阅
                    subscription = user_info.get('subscription')
                    if subscription and subscription.get('status') == 'active':
                        self.logger.warning('用户已有活跃订阅！')
                        self.logger.info(f'订阅类型: {subscription.get("plan")}')
                        return True  # 已激活，无需继续
                else:
                    self.logger.warning(f'/api/auth/me 返回: {me_resp.status_code}')
            except Exception as e:
                self.logger.warning(f'获取用户信息失败: {e}')
            
            # 模拟用户浏览Pro页面
            self.logger.debug('[延迟] 模拟用户查看Pro计划...')
            random_delay(2.0, 4.0)
            
            # 获取Stripe配置
            self.logger.info('[1/3] 获取Stripe配置')
            
            resp = self.session.get('https://cursor.com/api/auth/stripe', proxies=self.proxies, timeout=30)
            
            self.logger.debug(f'[响应] 状态码: {resp.status_code}')
            self.logger.debug(f'[响应] Content-Type: {resp.headers.get("content-type", "")}')
            
            if resp.status_code != 200:
                self.logger.error(f'获取失败: HTTP {resp.status_code}')
                self.logger.debug(f'响应内容: {resp.text[:500]}')
                return False
            
            # 解析JSON响应
            try:
                stripe_data = resp.json()
                self.logger.debug(f'[响应] JSON keys: {list(stripe_data.keys()) if isinstance(stripe_data, dict) else type(stripe_data)}')
            except Exception as e:
                self.logger.error(f'解析JSON失败: {e}')
                self.logger.debug(f'响应内容: {resp.text[:500]}')
                return False
            
            stripe_key = stripe_data.get('publishable_key')
            
            if not stripe_key:
                self.logger.warning('响应中未包含publishable_key')
                self.logger.debug(f'完整响应: {stripe_data}')
                
                # 使用文档中的公钥作为fallback（来自Cursor支付激活流程分析.md）
                stripe_key = 'pk_live_51Lb5LzB4TZWxSIGU4LcaRyvT5xW1Iw8Z3E1iOpuCblBLoLhoq3xQnt2U6sR0kfr6wwTdLdQCykfzNnw778PaO7n200tsRmVe72'
                self.logger.info('[Fallback] 使用文档中的Stripe公钥')
                self.logger.debug(f'公钥: {stripe_key[:50]}...')
            
            # 保存stripe_key供webhook使用
            self._current_stripe_key = stripe_key
            
            self.logger.success(f'Stripe公钥: {stripe_key[:50]}...')
            
            # 模拟用户决定购买
            self.logger.debug('[延迟] 模拟用户决定购买...')
            random_delay(1.0, 2.5)
            
            # 创建Checkout Session
            self.logger.info('[2/3] 创建Checkout Session')
            
            # 关键修复：使用试用流程而不是立即付费
            # 参考支付.har中的正确请求
            self.logger.info('[重要] 使用7天免费试用流程')
            
            resp = self.session.post(
                'https://cursor.com/api/checkout',
                json={
                    'tier': PLAN,                    # ✅ 使用"tier"而不是"plan"
                    'allowTrial': True,              # ✅ 启用试用
                    'allowAutomaticPayment': False   # ✅ 试用期不扣款
                },
                proxies=self.proxies,
                timeout=30
            )
            
            if resp.status_code != 200:
                self.logger.error(f'创建失败: {resp.status_code}')
                return False
            
            checkout_url = resp.json()
            session_id = checkout_url.split('/pay/')[1].split('#')[0]
            self.logger.success(f'Session ID: {session_id}')
            self.logger.info(f'Checkout URL: {checkout_url[:80]}...')
            
            # 尝试访问Checkout页面，提取真正的publishable_key
            self.logger.info('[提取] 访问Checkout页面获取正确的Stripe公钥...')
            
            try:
                checkout_resp = self.session.get(checkout_url, proxies=self.proxies, timeout=30, allow_redirects=True)
                self.logger.debug(f'[Checkout] 状态码: {checkout_resp.status_code}')
                
                if checkout_resp.status_code == 200:
                    # 尝试从HTML中提取真正的publishable_key
                    import re
                    
                    # 检查session_id是live还是test
                    is_live_session = session_id.startswith('cs_live_')
                    is_test_session = session_id.startswith('cs_test_')
                    
                    self.logger.debug(f'[Session] 环境: {"LIVE" if is_live_session else "TEST" if is_test_session else "UNKNOWN"}')
                    
                    # 提取所有公钥
                    all_keys = re.findall(r'"(pk_(live|test)_[a-zA-Z0-9]+)"', checkout_resp.text)
                    
                    if all_keys:
                        self.logger.debug(f'[提取] 找到 {len(all_keys)} 个公钥')
                        
                        # 根据session环境选择匹配的key
                        live_keys = [k[0] for k in all_keys if k[1] == 'live']
                        test_keys = [k[0] for k in all_keys if k[1] == 'test']
                        
                        self.logger.debug(f'[公钥] LIVE: {len(live_keys)}个, TEST: {len(test_keys)}个')
                        
                        real_stripe_key = None
                        
                        # 关键修复：HAR中使用的就是fallback的live key！
                        # 之前失败是因为Origin错误，现在Origin已修正
                        if live_keys:
                            # 找到live key
                            real_stripe_key = live_keys[0]
                            self.logger.success(f'找到LIVE公钥: {real_stripe_key[:50]}...')
                            
                            # 检查是否与fallback相同
                            if real_stripe_key == stripe_key:
                                self.logger.info('[验证] 提取的公钥与fallback一致（正确！）')
                            else:
                                self.logger.info('[更新] 使用Checkout页面中的LIVE公钥')
                                stripe_key = real_stripe_key
                        else:
                            # 没找到live key
                            if test_keys:
                                self.logger.warning(f'[提取] 只找到TEST公钥: {test_keys[0][:50]}...')
                            else:
                                self.logger.warning('[提取] 未找到任何公钥')
                            
                            # 关键：继续使用fallback的LIVE key
                            # 因为HAR中使用的就是这个key
                            # Origin已修正为checkout.stripe.com，应该能用
                            self.logger.info('[保持] 使用fallback的LIVE公钥')
                            self.logger.info('[修正] Origin已修正为checkout.stripe.com（关键！）')
                            # stripe_key保持不变
                    else:
                        self.logger.warning('[提取] 未在Checkout页面找到公钥')
                else:
                    self.logger.warning(f'Checkout页面访问异常: {checkout_resp.status_code}')
            except Exception as e:
                self.logger.warning(f'访问Checkout页面失败: {e}')
            
            # 模拟用户填写支付信息
            self.logger.debug('[延迟] 模拟用户填写信用卡信息...')
            random_delay(3.0, 6.0)
            
            # Stripe支付
            self.logger.info('[3/3] Stripe支付')
            
            # 初始化支付页面（关键：获取init_checksum）
            self.logger.info('[3.1] 初始化支付页面')
            
            init_url = f'https://api.stripe.com/v1/payment_pages/{session_id}/init'
            init_headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://checkout.stripe.com',
                'Referer': 'https://checkout.stripe.com/',
                'User-Agent': self.fingerprint['user_agent']
            }
            
            init_success = False
            init_checksum = None
            stripe_version = '90ba939846'  # 从HAR获取的Stripe.js版本
            
            try:
                # 关键修复：添加HAR中的所有必需参数
                init_data = {
                    'key': stripe_key,
                    'eid': 'NA',  # Event ID
                    'browser_locale': self.fingerprint.get('accept_language', 'en-US').split(',')[0],  # 例如: zh-CN
                    'browser_timezone': 'Asia/Shanghai',  # 或根据fingerprint动态设置
                    'redirect_type': 'url'
                }
                
                self.logger.debug(f'[Init] 请求参数: {init_data}')
                
                resp = self.session.post(
                    init_url,
                    data=init_data,
                    headers=init_headers,
                    proxies=self.proxies,
                    timeout=30
                )
                
                self.logger.debug(f'[Init] 状态码: {resp.status_code}')
                
                if resp.status_code == 200:
                    # 解析session信息
                    try:
                        session_data = resp.json()
                        mode = session_data.get('mode', 'unknown')
                        self.logger.success(f'支付模式: {mode}')
                        
                        # 提取订阅信息和金额
                        subscription_amount = 0  # 默认为0
                        line_items = session_data.get('line_items', {}).get('data', [])
                        if line_items:
                            item = line_items[0]
                            price = item.get('price', {})
                            unit_amount = price.get('unit_amount', 0)
                            subscription_amount = unit_amount  # 保存原始金额（分）
                            amount_display = unit_amount / 100
                            currency = price.get('currency', 'usd').upper()
                            interval = price.get('recurring', {}).get('interval', 'month')
                            self.logger.info(f'价格: ${amount_display} {currency}/{interval}')
                            self.logger.info(f'[金额] expected_amount将使用: {subscription_amount}')
                        
                        # 关键：从响应中提取checksum
                        init_checksum = session_data.get('init_checksum') or session_data.get('checksum')
                        if init_checksum:
                            self.logger.success(f'Init Checksum: {init_checksum[:30]}...')
                        
                        init_success = True
                    except Exception as e:
                        self.logger.warning(f'解析session信息失败: {e}')
                        subscription_amount = 0  # 失败时使用0
                else:
                    self.logger.warning(f'初始化失败: {resp.status_code}')
                    self.logger.debug(f'响应: {resp.text[:500]}')
                    
                    # Init失败但继续（尝试不带checksum）
                    self.logger.info('[继续] 尝试不带checksum继续')
            except Exception as e:
                self.logger.warning(f'初始化异常: {e}')
                self.logger.info('[继续] 尝试不带checksum继续')
            
            # 模拟用户填写
            self.logger.debug('[延迟] 模拟用户填写信用卡...')
            random_delay(2.0, 4.0)
            
            # 创建支付方式
            self.logger.info('[3.2] 创建支付方式')
            
            # 生成Stripe设备指纹（guid和muid）
            import uuid
            stripe_guid = str(uuid.uuid4())
            stripe_muid = str(uuid.uuid4())
            stripe_sid = str(uuid.uuid4())
            
            self.logger.debug(f'[指纹] GUID: {stripe_guid}')
            self.logger.debug(f'[指纹] MUID: {stripe_muid}')
            
            # 构造payment_method数据（包含完整地址信息 + 设备指纹 + client_attribution）
            data = {
                'type': 'card',
                'card[number]': card_info['number'],
                'card[cvc]': card_info['cvc'],
                'card[exp_month]': card_info['exp_month'],
                'card[exp_year]': card_info['exp_year'],
                'billing_details[name]': billing_details['name'],
                'billing_details[email]': billing_details['email'],
                'billing_details[address][country]': billing_details['address']['country'],
                'billing_details[address][postal_code]': billing_details['address']['postal_code'],
                'guid': stripe_guid,  # Stripe设备指纹
                'muid': stripe_muid,  # Stripe设备指纹
                'sid': stripe_sid,    # Stripe会话ID
                'key': stripe_key,
                # 关键参数（从HAR发现）：
                'payment_user_agent': f'stripe.js/{stripe_version}; stripe-js-v3/{stripe_version}; checkout',
                'client_attribution_metadata[client_session_id]': session_id,
                'client_attribution_metadata[checkout_session_id]': session_id,  # ✅ 添加 checkout_session_id
                'client_attribution_metadata[merchant_integration_source]': 'checkout',
                'client_attribution_metadata[merchant_integration_version]': 'hosted_checkout',
                'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
            }
            
            # 添加可选的地址字段（如果提供）
            if 'line1' in billing_details['address']:
                data['billing_details[address][line1]'] = billing_details['address']['line1']
            
            if 'city' in billing_details['address']:
                data['billing_details[address][city]'] = billing_details['address']['city']
            
            if 'state' in billing_details['address']:
                data['billing_details[address][state]'] = billing_details['address']['state']
            
            self.logger.debug('[Stripe] Payment Method字段:')
            self.logger.debug(f'  卡号: {card_info["number"]}')
            self.logger.debug(f'  姓名: {billing_details["name"]}')
            self.logger.debug(f'  国家: {billing_details["address"]["country"]}')
            if 'city' in billing_details['address']:
                self.logger.debug(f'  城市: {billing_details["address"].get("city", "未设置")}')
            
            # 正确的Headers（从HAR发现：应该是checkout.stripe.com，不是js.stripe.com）
            payment_method_headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://checkout.stripe.com',
                'Referer': 'https://checkout.stripe.com/',
                'User-Agent': self.fingerprint['user_agent']
            }
            
            resp = self.session.post(
                'https://api.stripe.com/v1/payment_methods',
                data=data,
                headers=payment_method_headers,
                proxies=self.proxies,
                timeout=30
            )
            
            self.logger.debug(f'[Payment Method] 状态码: {resp.status_code}')
            
            if resp.status_code != 200:
                error = resp.json().get('error', {}).get('message', resp.text)
                self.logger.error(f'创建支付方式失败: {error}')
                return False
            
            pm_id = resp.json().get('id')
            card = resp.json().get('card', {})
            self.logger.success(f'支付方式: {card.get("brand")} **** {card.get("last4")}')
            self.logger.info(f'Payment Method ID: {pm_id}')
            
            # 模拟用户确认支付前的思考
            self.logger.debug('[延迟] 模拟用户确认支付...')
            random_delay(1.5, 3.0)
            
            # 确认支付（endpoint是/confirm，需要version和checksum）
            self.logger.info('[3.3] 确认支付')
            
            # 根据HAR文件第678个请求，endpoint是/confirm
            confirm_url = f'https://api.stripe.com/v1/payment_pages/{session_id}/confirm'
            
            # 检查是否从/init获取到了金额
            if 'subscription_amount' not in locals():
                subscription_amount = None
                self.logger.warning('[金额] 未从/init获取到金额')
            else:
                self.logger.info(f'[金额] expected_amount: {subscription_amount}')
            
            # 构造请求数据（包含HAR中的所有关键参数）
            confirm_data = {
                'eid': 'NA',  # Event ID
                'payment_method': pm_id,
                'expected_payment_method_type': 'card',
                'guid': stripe_guid,  # 使用相同的设备指纹
                'muid': stripe_muid,
                'sid': stripe_sid,
                'key': stripe_key,
                'version': stripe_version,  # Stripe.js版本（必需）
                'referrer': 'https://cursor.com',  # 来源页面
                # 添加client_attribution_metadata
                'client_attribution_metadata[client_session_id]': session_id,
                'client_attribution_metadata[checkout_session_id]': session_id,  # ✅ 添加 checkout_session_id
                'client_attribution_metadata[merchant_integration_source]': 'checkout',
                'client_attribution_metadata[merchant_integration_version]': 'hosted_checkout',
                'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
            }
            
            # 只有当获取到金额时才添加expected_amount
            # 如果没有获取到，让Stripe自动计算
            if subscription_amount is not None:
                confirm_data['expected_amount'] = str(subscription_amount)
                self.logger.info(f'[发送] expected_amount: {subscription_amount}')
            else:
                self.logger.warning('[尝试] 不发送expected_amount，让Stripe自动计算')
            
            # 添加init_checksum（如果init成功）
            if init_checksum:
                confirm_data['init_checksum'] = init_checksum
                self.logger.debug(f'[Checksum] 已添加init_checksum: {init_checksum[:20]}...')
            else:
                self.logger.warning('[Checksum] 没有init_checksum，可能导致失败')
                self.logger.info('[尝试] 仍然尝试提交（不带checksum）')
            
            confirm_headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://checkout.stripe.com',
                'Referer': 'https://checkout.stripe.com/',
                'User-Agent': self.fingerprint['user_agent']
            }
            
            self.logger.debug(f'[Confirm] URL: {confirm_url}')
            self.logger.debug(f'[Confirm] Payment Method: {pm_id}')
            self.logger.debug(f'[Confirm] Expected Amount: 0 (试用期)')
            self.logger.debug(f'[Confirm] Version: {stripe_version}')
            self.logger.debug(f'[Confirm] 参数数量: {len(confirm_data)}')
            self.logger.debug(f'[Confirm] 参数列表: {list(confirm_data.keys())}')
            
            resp = self.session.post(
                confirm_url,
                data=confirm_data,
                headers=confirm_headers,
                proxies=self.proxies,
                timeout=30
            )
            
            self.logger.debug(f'[Confirm] 状态码: {resp.status_code}')
            
            if resp.status_code != 200:
                self.logger.error(f'确认失败: {resp.status_code}')
                
                # 尝试解析错误信息
                try:
                    error_data = resp.json()
                    error_msg = error_data.get('error', {}).get('message', '')
                    error_type = error_data.get('error', {}).get('type', '')
                    if error_msg:
                        self.logger.error(f'错误信息: {error_msg}')
                    if error_type:
                        self.logger.error(f'错误类型: {error_type}')
                    self.logger.debug(f'完整错误: {error_data}')
                except:
                    self.logger.debug(f'响应: {resp.text[:500]}')
                
                # 如果confirm失败，建议手动支付
                self.logger.info('')
                self.logger.info('='*60)
                self.logger.info('自动支付失败，可能原因：')
                self.logger.info('  1. 缺少js_checksum参数（由Stripe.js浏览器生成）')
                self.logger.info('  2. 缺少passive_captcha_token（反机器人验证）')
                self.logger.info('  3. 需要真实浏览器环境完成支付')
                self.logger.info('='*60)
                self.logger.info(f'Checkout URL: {checkout_url}')
                self.logger.info('')
                self.logger.info('建议手动完成支付:')
                self.logger.info('  1. 在浏览器中打开上面的URL')
                self.logger.info('  2. 填写信用卡信息')
                self.logger.info('  3. 完成支付（绑卡后自动激活Pro）')
                self.logger.info('='*60)
                
                # 等待用户手动操作
                try:
                    input('\n按Enter键继续（完成支付后）...')
                    # 验证订阅状态
                    return self._verify_subscription()
                except KeyboardInterrupt:
                    return False
            
            # 解析响应
            try:
                result = resp.json()
                self.logger.debug(f'[响应] {json.dumps(result, indent=2)[:500]}...')
                
                # 检查不同的状态字段
                status = result.get('status')
                state = result.get('state')
                intent_status = result.get('intent_status')
                payment_status = result.get('payment_object_status') or result.get('payment_status')
                
                self.logger.info(f'状态: state={state}, intent={intent_status}, payment={payment_status}')
                
                # 关键修复：试用订阅的成功状态判断
                # 试用期订阅：state="active" + payment="unpaid" = 成功
                # 付费订阅：intent_status="succeeded" + payment="succeeded" = 成功
                
                if state == 'active':
                    # 试用订阅已激活（state=active就是最终状态）
                    self.logger.success('✓ 试用订阅已激活！')
                    
                    subscription_id = result.get('subscription')
                    if subscription_id:
                        self.subscription_id = subscription_id
                        self.logger.success(f'订阅ID: {self.subscription_id}')
                    
                    # ✅ 修复：从多个可能的字段提取redirect_url
                    redirect_url = None
                    
                    # 1. 从poll中保存的URL
                    redirect_url = getattr(self, '_stripe_redirect_url', None)
                    
                    # 2. 从confirm响应中提取（多种可能的字段）
                    if not redirect_url:
                        redirect_url = result.get('redirect_to_url') or result.get('redirect_url') or result.get('return_url')
                    
                    # 3. 从checkout对象中提取
                    if not redirect_url and 'checkout' in result:
                        checkout = result['checkout']
                        redirect_url = checkout.get('success_url') or checkout.get('return_url')
                    
                    # 4. 手动构造跳转URL（使用session_id）
                    if not redirect_url:
                        # Stripe成功后会自动跳转回Cursor，我们手动构造这个URL
                        redirect_url = f'https://cursor.com/dashboard'
                        self.logger.info('[构造] 未在响应中找到redirect_url，使用默认dashboard')
                    
                    if redirect_url:
                        self.logger.info(f'[重定向] Stripe将跳转到: {redirect_url[:80]}...')
                        
                        # 模拟浏览器跟随跳转
                        if 'cursor.com' in redirect_url:
                            self.logger.info('[跟随] 访问Cursor完成激活...')
                            try:
                                redirect_resp = self.session.get(
                                    redirect_url,
                                    proxies=self.proxies,
                                    allow_redirects=True,
                                    timeout=30
                                )
                                self.logger.debug(f'[跳转] 状态码: {redirect_resp.status_code}')
                                self.logger.debug(f'[跳转] 最终URL: {redirect_resp.url[:80]}...')
                            except Exception as e:
                                self.logger.warning(f'[跳转] 访问失败: {e}（不影响激活）')
                        else:
                            self.logger.debug(f'[跳过] 非Cursor域名跳转: {redirect_url}')
                    else:
                        self.logger.debug('[重定向] 响应中未包含跳转URL')
                    
                    self.logger.success('='*60)
                    self.logger.success('7天免费试用已成功激活！')
                    self.logger.success('='*60)
                    self.logger.info('试用信息:')
                    self.logger.info('  - 试用期: 7天')
                    self.logger.info('  - 状态: 已激活')
                    self.logger.info('  - 费用: $0 (试用期免费)')
                    self.logger.info('  - 试用结束后将自动扣款 $20/月')
                    self.logger.info('')
                    
                    # ✅ 修复：增加webhook等待时间和重试
                    self.logger.info('[重要] 等待Cursor后端处理Stripe通知...')
                    self.logger.info('[策略] Stripe webhook处理通常需要30-60秒')
                    
                    # 先等待Stripe webhook API返回completed
                    webhook_completed = self._wait_for_webhook_completion(session_id, timeout=30)
                    
                    if webhook_completed:
                        self.logger.success('[Webhook API] 已返回completed！')
                        self.logger.info('[等待] 再等待10秒确保Cursor处理完成...')
                        time.sleep(10)
                    else:
                        self.logger.warning('[Webhook API] 30秒内未返回completed')
                        self.logger.info('[继续] Cursor后端可能仍在处理，等待30秒...')
                        time.sleep(30)  # 给Cursor后端充足时间处理webhook
                    
                    self.logger.info('')
                    
                    # 访问Dashboard和同步API
                    self.logger.info('[验证] 访问Dashboard确认激活...')
                    dashboard_ok = self._confirm_activation_on_dashboard()
                    
                    if dashboard_ok:
                        # 关键：调用API同步订阅状态
                        self.logger.info('')
                        sync_ok = self._sync_subscription_status()
                        
                        if sync_ok:
                            self.logger.success('='*60)
                            self.logger.success('✓ 激活完全成功！Pro已可用！')
                            self.logger.success('='*60)
                            return True
                        else:
                            # ✅ 修复：增加重试次数和延迟
                            self.logger.warning('[未发现订阅] 可能需要更多时间同步')
                            self.logger.info('[重试策略] 将尝试3次，每次间隔15秒')
                            
                            # 最多重试3次
                            for retry_attempt in range(1, 4):
                                self.logger.info(f'[重试 {retry_attempt}/3] 等待15秒后检查...')
                                time.sleep(15)
                                
                                self.logger.info(f'[重试 {retry_attempt}/3] 调用 /api/usage-summary')
                                retry_resp = self.session.get(
                                    'https://cursor.com/api/usage-summary',
                                    proxies=self.proxies,
                                    timeout=30
                                )
                                
                                if retry_resp.status_code == 200:
                                    try:
                                        usage_data = retry_resp.json()
                                        membership_type = usage_data.get('membershipType')
                                        
                                        self.logger.info(f'[检测] membershipType: {membership_type}')
                                        
                                        if membership_type in ['free_trial', 'pro', 'business']:
                                            self.logger.success(f'[成功] membershipType已更新为: {membership_type}')
                                            self.logger.success('[确认] 订阅信息已同步！')
                                            self.logger.success('='*60)
                                            self.logger.success('✓ 激活完全成功！Pro已可用！')
                                            self.logger.success('='*60)
                                            return True
                                        else:
                                            self.logger.warning(f'[尝试{retry_attempt}] 仍是: {membership_type}')
                                    except Exception as e:
                                        self.logger.warning(f'[尝试{retry_attempt}] 解析失败: {e}')
                            
                            # 所有重试都失败
                            self.logger.error('='*60)
                            self.logger.error('❌ 订阅同步超时！')
                            self.logger.error('='*60)
                            self.logger.warning('[Stripe端] 订阅已创建（state=active）')
                            self.logger.warning('[Cursor端] 订阅状态未更新（membershipType=free）')
                            self.logger.warning('')
                            self.logger.info('[可能原因]')
                            self.logger.info('  1. Stripe webhook 延迟（通常需要1-2分钟）')
                            self.logger.info('  2. Cursor后端处理队列堵塞')
                            self.logger.info('  3. 卡号被拒（虽然Stripe返回active）')
                            self.logger.warning('')
                            self.logger.info('[解决方案]')
                            self.logger.info('  1. 等待2-5分钟后访问: https://cursor.com/dashboard')
                            self.logger.info('  2. 检查邮箱是否收到Cursor的激活邮件')
                            self.logger.info('  3. 如果长时间未激活，尝试重新绑卡')
                            self.logger.info('='*60)
                            return False  # 返回False表示未完全成功
                    else:
                        self.logger.warning('[提示] Dashboard访问失败，但订阅已激活')
                        self.logger.info('建议: 手动访问 https://cursor.com/dashboard 确认')
                        return True  # state=active就算成功
                    
                elif state == 'processing_subscription':
                    # 需要poll等待succeeded（参考OK.har的流程）
                    self.logger.info('[分析] confirm返回state=processing_subscription')
                    self.logger.info('[需要] poll轮询等待state变为succeeded')
                    self.logger.info('')
                    
                    subscription_id = result.get('subscription')
                    if subscription_id:
                        self.subscription_id = subscription_id
                        self.logger.success(f'订阅ID: {self.subscription_id}')
                    
                    # 步骤1：Poll轮询支付状态
                    self.logger.info('\n[步骤1] 轮询支付状态...')
                    poll_completed = self._poll_payment_state(session_id)
                    
                    if poll_completed:
                        self.logger.success('[Poll] 支付状态已完成')
                    else:
                        self.logger.warning('[Poll] 超时，继续尝试webhook')
                    
                    # 步骤2：等待webhook
                    self.logger.info('\n[步骤2] 等待Stripe webhook处理完成...')
                    webhook_completed = self._wait_for_webhook_completion(session_id)
                    
                    if webhook_completed:
                        self.logger.success('[Webhook] 已完成！')
                        
                        # 访问dashboard确认激活
                        self.logger.info('\n[步骤3] 访问Dashboard确认激活...')
                        dashboard_ok = self._confirm_activation_on_dashboard()
                        
                        if dashboard_ok:
                            self.logger.success('='*60)
                            self.logger.success('✓ 激活完全成功！Pro已可用！')
                            self.logger.success('='*60)
                            return True
                        else:
                            self.logger.warning('[提示] Webhook完成但dashboard访问失败')
                            self.logger.info('建议: 手动访问 https://cursor.com/dashboard 确认')
                            return True  # webhook完成就算成功
                    else:
                        self.logger.warning('[超时] Webhook未在预期时间内完成')
                        self.logger.info('建议: 稍后访问 https://cursor.com/dashboard 确认')
                        return True  # 订阅已激活，只是webhook慢
                    
                elif state == 'processing_subscription':
                    # 正在处理订阅（也是成功的一种状态）
                    self.logger.info('[处理中] 订阅正在处理...')
                    
                    # 等待webhook
                    self.logger.info('[等待] Webhook处理...')
                    webhook_completed = self._wait_for_webhook_completion(session_id)
                    
                    if webhook_completed:
                        self.logger.success('[完成] Webhook已处理')
                        self._confirm_activation_on_dashboard()
                        return True
                    else:
                        self.logger.warning('[超时] 建议手动确认')
                        return True
                    
                elif intent_status == 'succeeded' or payment_status in ['succeeded', 'paid']:
                    # 付费订阅成功
                    self.logger.success('支付已提交成功！')
                    
                    subscription_id = result.get('subscription')
                    if subscription_id:
                        self.subscription_id = subscription_id
                        self.logger.success(f'订阅ID: {self.subscription_id}')
                    
                    # 等待订阅生效
                    self.logger.info('[等待] Stripe处理订阅中...')
                    time.sleep(5)
                    
                    # 验证订阅
                    return self._verify_subscription()
                else:
                    self.logger.warning(f'支付状态异常: {state}')
                    self.logger.info('可能需要更多时间处理，或者需要在浏览器中完成')
                    
                    # 建议手动检查
                    self.logger.info('')
                    self.logger.info('建议：')
                    self.logger.info('  1. 访问 https://cursor.com/dashboard')
                    self.logger.info('  2. 检查Pro是否已激活')
                    self.logger.info(f'  3. 或访问Checkout URL: {checkout_url}')
                    
                    return False
                    
            except Exception as e:
                self.logger.error(f'解析响应失败: {e}')
                self.logger.debug(f'原始响应: {resp.text[:500]}')
                return False
                
        except Exception as e:
            self.logger.error(f'激活Pro失败: {e}')
            return False


def load_card_info():
    """从信用卡.txt加载配置，或使用卡片生成器"""
    card_file = '信用卡.txt'
    
    # 尝试加载 generate_card_info 模块
    try:
        from generate_card_info import CardGenerator
        
        if not os.path.exists(card_file):
            print('\n[提示] 未找到 信用卡.txt，使用卡片生成器\n')
            
            # 使用卡片生成器生成 Amex 379240 开头的卡
            generator = CardGenerator(bin_pattern='379240xxxxxxxxx')
            
            # 随机选择地区：60% SG, 30% HK, 10% US
            import random
            rand = random.random()
            if rand < 0.6:
                country = 'SG'
            elif rand < 0.9:
                country = 'HK'
            else:
                country = 'US'
            
            card_data = generator.generate_complete_info(country)
            card = card_data['card']
            addr = card_data['billing_address']
            
            print(f'[生成] 卡号: {card["card_number_formatted"]}')
            print(f'[生成] 过期: {card["expiry"]}')
            print(f'[生成] CVV: {card["cvv"]}')
            print(f'[生成] 持卡人: {addr["name"]}')
            print(f'[生成] 国家: {addr["country"]}')
            print()
            
            return {
                'number': card['card_number'],
                'exp_month': int(card['month']),
                'exp_year': int('20' + card['year']),
                'cvc': card['cvv']
            }, {
                'name': addr['name'],
                'country': addr['country'],
                'postal_code': addr['zip'],
                'line1': addr['address1'],
                'city': addr['city'],
                'state': addr['state']
            }
    except ImportError:
        print('\n[警告] 未找到 generate_card_info.py，使用默认测试卡\n')
        if not os.path.exists(card_file):
            return {
                'number': '4242424242424242',
                'exp_month': 12,
                'exp_year': 2025,
                'cvc': '123'
            }, {
                'name': 'Test User',
                'country': 'US',
                'postal_code': '12345'
            }
    
    print(f'\n[读取] {card_file}...')
    
    try:
        with open(card_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        card_info = {}
        billing = {}
        
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if ':' in line or '：' in line:
                key, value = line.replace('：', ':').split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if '卡号' in key or 'number' in key:
                    card_info['number'] = value.replace(' ', '').replace('-', '')
                elif '月份' in key or 'month' in key:
                    card_info['exp_month'] = int(value)
                elif '年份' in key or 'year' in key:
                    card_info['exp_year'] = int(value)
                elif 'cvc' in key or '安全码' in key:
                    card_info['cvc'] = value
                elif '姓名' in key or 'name' in key:
                    billing['name'] = value
                elif '国家' in key or 'country' in key:
                    billing['country'] = value
                elif '邮编' in key or 'postal' in key or 'zip' in key:
                    billing['postal_code'] = value
                elif '地址' in key or 'line1' in key or 'address' in key:
                    billing['line1'] = value
                elif '城市' in key or 'city' in key:
                    billing['city'] = value
                elif '州' in key or '省' in key or 'state' in key:
                    billing['state'] = value
        
        # 设置默认值
        billing.setdefault('name', 'Test User')
        billing.setdefault('country', 'US')
        billing.setdefault('postal_code', '12345')
        billing.setdefault('line1', '123 Main St')
        billing.setdefault('city', 'San Francisco')
        billing.setdefault('state', 'CA')
        
        print(f'  [OK] 卡号: {card_info.get("number")}')
        print(f'  [OK] 过期: {card_info.get("exp_month")}/{card_info.get("exp_year")}\n')
        
        return card_info, billing
        
    except Exception as e:
        print(f'  [错误] {e}\n')
        return {
            'number': '4242424242424242',
            'exp_month': 12,
            'exp_year': 2025,
            'cvc': '123'
        }, {
            'name': 'Test User',
            'country': 'US',
            'postal_code': '12345'
        }


def main():
    """主函数"""
    
    print('\n' + '='*60)
    print('Cursor 自动注册并激活Pro - 最终版（随机邮箱）')
    print('='*60)
    print()
    
    if not HAS_CURL_CFFI:
        print('[重要] 强烈建议安装curl_cffi！')
        print('[命令] pip install curl_cffi')
        print()
        choice = input('继续使用requests（可能失败）? (y/n): ').strip().lower()
        if choice != 'y':
            return
        print()
    
    logger = Logger()
    
    # 加载信用卡
    card_info, billing = load_card_info()
    
    # 获取代理IP（如果启用）
    proxy = None
    if USE_PROXY:
        proxy = get_proxy_ip(PROXY_API_URL, logger)
        if proxy:
            logger.success(f'将使用代理: {proxy}')
            logger.info('[提示] 使用代理IP可能避免触发手机验证')
        else:
            logger.warning('[提示] 代理获取失败，继续使用直连（可能触发手机验证）')
        logger.info('')
    
    # 创建邮箱
    email_service = None
    if USE_RANDOM_EMAIL:
        # 使用随机邮箱（避免tmpmail被识别）
        email = generate_random_email()
        logger.success(f'[随机邮箱] {email}')
        logger.info('[提示] 使用随机邮箱域名，不依赖邮件服务')
        logger.warning('[注意] 无法接收邮件，仅用于注册（如果需要验证码会失败）')
        logger.info('')
    else:
        # 根据配置选择邮件服务
        if EMAIL_SERVICE == 'gptmail':
            logger.info('[邮件服务] 使用 GPTMail')
            email_service = GPTMailClient(GPTMAIL_BASE_URL, logger)
        else:
            logger.info('[邮件服务] 使用 tmpmail.vip')
            email_service = TempEmail(TMPMAIL_API_KEY, TMPMAIL_BASE_URL, logger)

        email = email_service.create(prefer_com=False)  # ✅ 使用所有后缀域名
        if not email:
            logger.error('[邮箱] 创建失败')
            return
        logger.info('')
    
    # 准备账单信息（包含完整地址）
    billing_details = {
        'name': billing['name'],
        'email': email,
        'address': {
            'country': billing['country'],
            'postal_code': billing['postal_code'],
            'line1': billing.get('line1', '123 Main St'),
            'city': billing.get('city', 'San Francisco'),
            'state': billing.get('state', 'CA')
        }
    }
    
    # 执行注册
    logger.info('[注册] 开始')
    logger.info(f'邮箱: {email}')
    if proxy:
        logger.info(f'代理: {proxy}')
    logger.info('')
    
    cursor = CursorAuto(logger, proxy)
    
    # 初始化
    if not cursor.init_auth_session():
        logger.error('初始化失败')
        if email_service:
            email_service.delete()
        return
    
    # 步骤间的自然过渡（已在函数内部添加延迟）
    
    # 提交邮箱
    if not cursor.submit_email(email):
        logger.error('提交邮箱失败')
        if email_service:
            email_service.delete()
        return
    
    # 获取验证码
    if USE_RANDOM_EMAIL:
        logger.warning('[随机邮箱] 无法接收验证码')
        logger.info('[提示] 如果Cursor需要邮箱验证码，注册将失败')
        logger.info('[解决] 请设置 USE_RANDOM_EMAIL = False 使用tmpmail')
        logger.info('')
        # 尝试继续（某些情况可能不需要验证码）
        code = None
    else:
        # 等待邮箱接收验证码（邮件服务器处理时间）
        logger.debug('[延迟] 等待邮件服务器处理...')
        random_delay(2.0, 4.0)

        code = email_service.get_verification_code(timeout=60)  # ✅ 缩短超时：120秒 -> 60秒
        if not code:
            logger.error('未获取到验证码')
            email_service.delete()
            return
    
    # 提交验证码（如果有）
    if code:
        if not cursor.submit_verification_code(code):
            # 检查是否触发手机验证
            if cursor.phone_verification_triggered:
                logger.error('触发手机验证，注册失败')
                logger.info('[处理] 将该邮箱域名加入黑名单')
                add_to_blacklist(email)
            else:
                logger.error('提交验证码失败')

            if email_service:
                email_service.delete()
            return
    else:
        logger.info('[跳过] 无验证码，尝试直接继续...')

    # 额外检查：即使验证码提交成功，也检查是否触发了手机验证
    if cursor.phone_verification_triggered:
        logger.warning('验证码提交后触发手机验证')
        logger.info('[处理] 将该邮箱域名加入黑名单')
        add_to_blacklist(email)
        if email_service:
            email_service.delete()
        return

    logger.info('')
    
    # 检查是否需要激活Pro
    if ACTIVATE_PRO:
        logger.info('[Pro] 开始激活（绑定信用卡）')
        logger.info('[提示] 绑卡后会自动激活Pro（不会立即扣钱）')
        # 登录成功后的自然过渡（已在activate_pro内部添加延迟）
        
        # 激活Pro
        if not cursor.activate_pro(card_info, billing_details):
            logger.warning('自动绑卡失败')
            logger.info('')
            logger.info('='*60)
            logger.info('建议：手动完成绑卡')
            logger.info('='*60)
            logger.info('')
            logger.info('步骤：')
            logger.info('  1. 访问 https://cursor.com/pricing')
            logger.info('  2. 点击 "Subscribe" 或 "Upgrade"')
            logger.info('  3. 填写信用卡信息')
            logger.info('  4. 完成绑卡（不会立即扣钱）')
            logger.info('  5. Pro功能会自动激活')
            logger.info('')
            logger.info('账号信息：')
            logger.info(f'  邮箱: {email}')
            logger.info(f'  Token: {cursor.session_token}')
            logger.info('='*60)
        else:
            # 激活成功
            logger.info('')
            logger.info('='*60)
            logger.success('Pro激活成功！')
            logger.info('='*60)
            logger.info('')
            logger.info('账号信息:')
            logger.info(f'  邮箱: {email}')
            logger.info(f'  Token: {cursor.session_token}')
            if cursor.subscription_id:
                logger.info(f'  订阅ID: {cursor.subscription_id}')
            logger.info('='*60)
    else:
        # 只注册账号，生成订阅链接
        logger.info('[模式] 只注册账号，生成订阅链接')
        logger.info('[提示] 需要手动完成支付激活Pro')
        logger.info('')
        
        # 生成订阅链接
        checkout_url = cursor.generate_subscription_link()
        
        if checkout_url:
            # 保存到文件
            try:
                with open('cursor-2-cookies.txt', 'a', encoding='utf-8') as f:
                    f.write('\n' + '='*80 + '\n')
                    f.write(f'注册时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
                    f.write(f'邮箱 (cursorAuth/cachedEmail): {email}\n')
                    f.write(f'AccessToken (cursorAuth/accessToken): {cursor.access_token if cursor.access_token else "未获取"}\n')
                    f.write(f'RefreshToken (cursorAuth/refreshToken): {cursor.refresh_token if cursor.refresh_token else "未获取"}\n')
                    f.write(f'SessionToken (WorkosCursorSessionToken): {cursor.session_token}\n')
                    f.write(f'订阅链接: {checkout_url}\n')
                    f.write('='*80 + '\n')
                
                logger.success('账号信息已保存到 cursor-2-cookies.txt')
                logger.info('')
                logger.info('='*60)
                logger.success('注册完成！')
                logger.info('='*60)
                logger.info('')
                logger.info('账号信息:')
                logger.info(f'  邮箱: {email}')
                logger.info(f'  AccessToken: {cursor.access_token[:50] if cursor.access_token else "未获取"}...')
                logger.info(f'  RefreshToken: {cursor.refresh_token[:50] if cursor.refresh_token else "未获取"}...')
                logger.info(f'  SessionToken: {cursor.session_token[:50]}...')
                logger.info(f'  订阅链接: {checkout_url}')
                logger.info('')
                logger.info('下一步:')
                logger.info('  1. 在浏览器中打开订阅链接')
                logger.info('  2. 填写信用卡信息完成支付')
                logger.info('  3. 7天免费试用会立即激活')
                logger.info('='*60)
            except Exception as e:
                logger.error(f'保存文件失败: {e}')
        else:
            logger.error('生成订阅链接失败')
            logger.info('')
            logger.info('='*60)
            logger.info('账号信息:')
            logger.info(f'  邮箱: {email}')
            logger.info(f'  Token: {cursor.session_token}')
            logger.info('')
            logger.info('手动激活步骤:')
            logger.info('  1. 访问 https://cursor.com/pricing')
        logger.info('  2. 绑定信用卡激活Pro')
        logger.info('='*60)
    
    # 清理（如果使用tmpmail）
    if not USE_RANDOM_EMAIL:
        try:
            delete = input('\n删除临时邮箱? (y/n): ').strip().lower()
            if delete == 'y':
                email_service.delete()
        except:
            pass


def register_single_account(task_id: int, card_info: Dict, billing: Dict, use_proxy: bool = False) -> Dict:
    """注册单个账号（线程安全，带超时保护）

    Args:
        task_id: 任务ID
        card_info: 信用卡信息
        billing: 账单信息
        use_proxy: 是否使用代理

    Returns:
        结果字典
    """
    import threading
    import logging
    import signal

    # 创建静默的内存日志（不输出到文件和控制台）
    logger_name = f'CursorBatch_{task_id}_{threading.get_ident()}'
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.CRITICAL)  # 只记录严重错误
    logger.handlers.clear()  # 清除所有handler

    # 包装成与原Logger兼容的对象
    class SilentLogger:
        def debug(self, msg): pass
        def info(self, msg): pass
        def warning(self, msg): pass
        def error(self, msg): pass
        def success(self, msg): pass
        def step(self, num, total, title): pass

    logger = SilentLogger()

    result = {
        'task_id': task_id,
        'success': False,
        'email': None,
        'session_token': None,
        'access_token': None,
        'refresh_token': None,
        'subscription_id': None,
        'checkout_url': None,
        'error': None
    }

    try:
        logger.info(f'[任务{task_id}] 开始注册')
        
        # 获取代理（如果启用）
        proxy = None
        if use_proxy:
            proxy = get_proxy_ip(PROXY_API_URL, logger)
            if proxy:
                logger.success(f'代理: {proxy}')
        
        # 创建邮箱
        email_service = None
        if USE_RANDOM_EMAIL:
            email = generate_random_email()
            logger.success(f'邮箱: {email}')
        else:
            # 根据配置选择邮件服务
            if EMAIL_SERVICE == 'gptmail':
                email_service = GPTMailClient(GPTMAIL_BASE_URL, logger)
            else:
                email_service = TempEmail(TMPMAIL_API_KEY, TMPMAIL_BASE_URL, logger)

            email = email_service.create(prefer_com=False)  # ✅ 使用所有后缀域名
            if not email:
                raise Exception('创建邮箱失败')
        
        result['email'] = email
        
        # 准备账单信息
        billing_details = {
            'name': billing['name'],
            'email': email,
            'address': {
                'country': billing['country'],
                'postal_code': billing['postal_code'],
                'line1': billing.get('line1', '123 Main St'),
                'city': billing.get('city', 'San Francisco'),
                'state': billing.get('state', 'CA')
            }
        }
        
        # 创建Cursor实例
        cursor = CursorAuto(logger, proxy)
        
        # 初始化
        if not cursor.init_auth_session():
            raise Exception('初始化失败')
        
        # 提交邮箱
        if not cursor.submit_email(email):
            raise Exception('提交邮箱失败')
        
        # 获取验证码（添加额外的异常捕获）
        code = None
        if not USE_RANDOM_EMAIL:
            try:
                random_delay(2.0, 4.0)
                code = email_service.get_verification_code(timeout=60)  # ✅ 缩短超时：120秒 -> 60秒
                if not code:
                    raise Exception('未获取到验证码')
            except Exception as e:
                # 获取验证码失败，记录错误并继续（避免卡住）
                logger.error(f'[任务{task_id}] 获取验证码异常: {e}')
                raise Exception(f'获取验证码失败: {str(e)[:50]}')

        # 提交验证码
        if code:
            try:
                if not cursor.submit_verification_code(code):
                    # 检查是否触发手机验证
                    if cursor.phone_verification_triggered:
                        logger.info(f'[任务{task_id}] 触发手机验证，将域名加入黑名单')
                        add_to_blacklist(email)
                        raise Exception('触发手机验证')
                    else:
                        raise Exception('提交验证码失败')
            except Exception as e:
                # 提交验证码失败，记录并退出
                logger.error(f'[任务{task_id}] 提交验证码异常: {e}')
                raise

        # 额外检查：即使验证码提交成功，也检查是否触发了手机验证
        if cursor.phone_verification_triggered:
            logger.info(f'[任务{task_id}] 验证码提交后触发手机验证，将域名加入黑名单')
            add_to_blacklist(email)
            raise Exception('触发手机验证')
        
        # 保存token
        result['session_token'] = cursor.session_token
        result['access_token'] = cursor.access_token
        result['refresh_token'] = cursor.refresh_token
        
        # 激活Pro（如果启用）
        if ACTIVATE_PRO:
            if cursor.activate_pro(card_info, billing_details):
                result['subscription_id'] = cursor.subscription_id
                logger.success(f'[任务{task_id}] Pro激活成功')
            else:
                logger.warning(f'[任务{task_id}] Pro激活失败')
        else:
            # 只生成订阅链接
            checkout_url = cursor.generate_subscription_link()
            result['checkout_url'] = checkout_url
        
        result['success'] = True

        # 清理邮箱
        if email_service and not USE_RANDOM_EMAIL:
            try:
                email_service.delete()
            except:
                pass

    except KeyboardInterrupt:
        # 用户中断，立即返回
        result['error'] = '用户中断'
        return result
    except Exception as e:
        # 捕获所有异常，确保线程能正常退出
        result['error'] = str(e)[:100]  # 限制错误信息长度
    except:
        # 捕获未知异常
        result['error'] = '未知异常'
    finally:
        # 确保清理资源
        if email_service and not USE_RANDOM_EMAIL:
            try:
                email_service.delete()
            except:
                pass

    return result


def batch_register(count: int, threads: int = 3, use_proxy: bool = False):
    """批量注册账号（并发）
    
    Args:
        count: 注册数量
        threads: 并发线程数（默认3）
        use_proxy: 是否使用代理
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
    from threading import Lock
    import sys
    
    print('\n' + '='*70)
    print('  Cursor 批量注册 - 并发模式')
    print('='*70)
    print(f'  注册数量: {count}  |  并发线程: {threads}  |  代理: {"开启" if use_proxy else "关闭"}  |  激活Pro: {"是" if ACTIVATE_PRO else "否"}')
    print('='*70)
    print()
    
    # 提前加载信用卡信息（在禁用print之前）
    print('[配置] 加载信用卡信息...')
    card_info, billing = load_card_info()
    print('[完成] 配置加载完成\n')
    
    # 结果统计
    results = []
    success_count = 0
    fail_count = 0
    active_threads = 0
    lock = Lock()
    
    # 文件写入锁（避免多线程写入冲突）
    file_write_lock = Lock()

    # 实时写入函数（每完成一个就保存，线程安全）
    def save_result_immediately(result):
        """立即保存单个结果到文件（线程安全）"""
        if not result['success']:
            return

        try:
            with file_write_lock:  # ✅ 使用锁保护文件写入
                # 1. 订阅链接.txt
                if result.get('checkout_url'):
                    with open('订阅链接.txt', 'a', encoding='utf-8') as f:
                        f.write(f"{result['checkout_url']}\n")
                        f.flush()

                # 2. 账号信息.txt
                with open('账号信息.txt', 'a', encoding='utf-8') as f:
                    f.write(f"邮箱: {result['email']}\n")
                    f.write(f"SessionToken: {result['session_token']}\n")
                    if result.get('access_token'):
                        f.write(f"AccessToken: {result['access_token']}\n")
                    f.write('\n')  # 空行分隔
                    f.flush()

                # 3. 账号SessionToken.txt
                if result.get('session_token'):
                    with open('账号SessionToken.txt', 'a', encoding='utf-8') as f:
                        f.write(f"{result['session_token']}\n")
                        f.flush()
        except Exception as e:
            pass  # 静默处理写入错误
    
    start_time = time.time()
    
    # 保存原始print函数（用于进度框输出和黑名单通知）
    import builtins
    original_print = builtins.print
    builtins.__original_print__ = original_print  # ✅ 保存到builtins，供add_to_blacklist使用
    
    # 进度条字符
    def get_progress_bar(percent, width=25):
        filled = int(width * percent / 100)
        bar = '█' * filled + '░' * (width - filled)
        return bar
    
    # 清除多行（向上移动光标并清除）
    def clear_lines(n):
        for _ in range(n):
            sys.stdout.write('\033[F')  # 光标上移一行
            sys.stdout.write('\033[K')  # 清除当前行
    
    # 实时进度显示（固定4行）
    def update_progress(completed, total, active):
        with lock:
            elapsed = time.time() - start_time
            percent = (completed / total) * 100
            
            # 计算预计剩余时间
            if completed > 0:
                avg_time = elapsed / completed
                remaining = avg_time * (total - completed)
                eta_str = f"{int(remaining)}秒" if remaining < 300 else f"{remaining/60:.1f}分钟"
            else:
                eta_str = "计算中..."
            
            # 进度条
            bar = get_progress_bar(percent)
            
            # 清除之前的4行输出
            if completed > 0:
                clear_lines(4)
            
            # 使用original_print直接输出（绕过禁用）
            original_print(f"┌{'─'*68}┐")
            original_print(f"│ 线程: {active}/{threads} 运行中  │  进度: {completed}/{total} ({percent:.1f}%)  {bar} │")
            original_print(f"│ ✓ 成功: {success_count:3d}  │  ✗ 失败: {fail_count:3d}  │  耗时: {int(elapsed):4d}秒  │  预计剩余: {eta_str:>10s} │")
            original_print(f"└{'─'*68}┘")
            
            sys.stdout.flush()
    
    # 批量模式：禁用所有print输出（只保留进度框）
    builtins.print = lambda *args, **kwargs: None  # 禁用print
    
    # 初始显示（禁用print之后）
    original_print()
    update_progress(0, count, 0)
    
    # 使用线程池执行（添加超时保护）
    with ThreadPoolExecutor(max_workers=threads) as executor:
        # 提交所有任务
        futures = {
            executor.submit(register_single_account, i+1, card_info, billing, use_proxy): i+1
            for i in range(count)
        }

        completed = 0
        active_threads = threads  # 初始时所有线程都活跃

        # 处理完成的任务（添加超时）
        try:
            for future in as_completed(futures):  # ✅ 移除总超时，单个任务控制超时
                task_id = futures[future]

                try:
                    # 等待任务完成（最多等待150秒 = 2.5分钟）
                    # 这个时间应该足够完成：创建邮箱(10s) + 提交邮箱(30s) + 等待验证码(60s) + 提交验证码(30s) + 激活Pro(20s)
                    result = future.result(timeout=150)
                    results.append(result)

                    with lock:
                        if result['success']:
                            success_count += 1
                            # 立即保存成功的结果
                            save_result_immediately(result)
                        else:
                            fail_count += 1

                except TimeoutError:
                    # 单个任务执行超过2.5分钟，认为卡住
                    with lock:
                        fail_count += 1
                    results.append({
                        'task_id': task_id,
                        'success': False,
                        'error': '任务执行超时（超过2.5分钟）'
                    })
                    # 注意：已经运行的线程无法被取消，但不会阻塞主进程
                except Exception as e:
                    with lock:
                        fail_count += 1
                    results.append({
                        'task_id': task_id,
                        'success': False,
                        'error': str(e)[:100]
                    })

                completed += 1

                # 计算当前活跃线程数
                remaining_tasks = count - completed
                active_threads = min(threads, remaining_tasks)

                update_progress(completed, count, active_threads)

        except KeyboardInterrupt:
            # 用户中断，取消所有未完成任务
            original_print('\n[中断] 正在停止所有任务...')
            for future in futures:
                future.cancel()
            raise
    
    # 恢复print函数
    builtins.print = original_print

    print()

    # 统计耗时
    elapsed = time.time() - start_time

    # 加载黑名单统计
    blacklist = load_domain_blacklist()

    print()
    print('='*70)
    print('  批量注册完成！')
    print('='*70)
    print(f'  总数: {count}  |  成功: {success_count}  |  失败: {fail_count}')
    print(f'  耗时: {int(elapsed)}秒 ({elapsed/60:.1f}分钟)  |  平均: {elapsed/count:.1f}秒/个')
    if blacklist:
        print(f'  域名黑名单: {len(blacklist)}个（触发手机验证）')
    print('='*70)
    print()
    print(f'✓ 结果已实时保存到以下文件:')
    print(f'  - 订阅链接.txt ({success_count}个)')
    print(f'  - 账号信息.txt ({success_count}个)')
    print(f'  - 账号SessionToken.txt ({success_count}个)')
    if blacklist:
        print(f'  - {BLACKLIST_FILE} ({len(blacklist)}个域名)')
        print(f'    黑名单域名: {", ".join(sorted(blacklist))}')
    print()
    
    # 显示成功的账号
    if success_count > 0:
        print('  【本次成功账号预览】')
        for i, result in enumerate([r for r in results if r['success']][:5], 1):
            print(f'    {i}. {result["email"]}')
        if success_count > 5:
            print(f'    ... 还有 {success_count - 5} 个账号')
        print()


if __name__ == '__main__':
    try:
        import sys
        
        # 检查命令行参数
        if len(sys.argv) > 1:
            # 批量注册模式
            if sys.argv[1] == 'batch':
                count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
                threads = int(sys.argv[3]) if len(sys.argv) > 3 else 3
                
                batch_register(count, threads, USE_PROXY)
            else:
                print('用法:')
                print('  单个注册: python 自动注册激活_最终版-修复webhook.py')
                print('  批量注册: python 自动注册激活_最终版-修复webhook.py batch [数量] [线程数]')
                print()
                print('示例:')
                print('  python 自动注册激活_最终版-修复webhook.py batch 10 3')
                print('  (注册10个账号，使用3个并发线程)')
        else:
            # 单个注册模式
            main()
    
    except KeyboardInterrupt:
        print('\n\n[中断]')
    except Exception as e:
        print(f'\n[错误] {e}')
        import traceback
        traceback.print_exc()

