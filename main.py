import requests
import json
import time
import random
import os
import argparse
import logging
import sys
from datetime import datetime
from urllib.parse import unquote

# 配置文件路径
current_path = os.path.realpath(__file__)
directory_path = os.path.dirname(current_path)
ACCOUNTS_FILE = os.path.join(directory_path,'weibo_accounts.json')  # 存储多账号信息
TOPICS_FILE_PREFIX = os.path.join(directory_path,'supertopics_')    # 每个账号的超话列表文件前缀
RESULTS_DIR = os.path.join(directory_path,'results')                # 结果保存目录
LOGS_DIR = os.path.join(directory_path,'logs')                      # 日志保存目录

# 请求头，根据需要修改
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0 115Browser/35.3.0.2',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Connection': 'keep-alive'    
}

class WeiboSuperTopicSigner:
    def __init__(self, account_name=None, logger=None, account_uid=None):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.cookies = None
        self.account_name = account_name or "default"
        self.account_uid = account_uid
        self.topics_file = f"{TOPICS_FILE_PREFIX}{self.account_name}.json"
        self.logger = logger or logging.getLogger(__name__)
        self.sign_results = []  # 存储签到结果

    # 读取账号
    def load_cookies(self, cookies_dict):
        """加载cookies字典"""
        try:
            if cookies_dict:
                # 将字典转换为CookieJar
                self.cookies = requests.utils.cookiejar_from_dict(cookies_dict)
                self.session.cookies.update(self.cookies)
                self.logger.info(f"[{self.account_name}] Cookies加载成功")
                return True
            else:
                self.logger.error(f"[{self.account_name}] 错误: 未提供cookies")
                return False
        except Exception as e:
            self.logger.error(f"[{self.account_name}] 加载Cookies时出错: {str(e)}", exc_info=True)
            return False
    
    def check_login(self):
        """检查登录状态"""
        url = "https://weibo.com/"
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                # 检查页面中是否包含登录用户的标识
                if self.account_uid == response.headers.get('x-bypass-uid'):
                    self.logger.info(f"[{self.account_name}] 登录成功")
                    return True
                else:
                    self.logger.error(f"[{self.account_name}] 登录状态异常: 页面内容异常")
            else:
                self.logger.error(f"[{self.account_name}] 登录状态检查失败: {response.status_code}")
        except Exception as e:
            self.logger.error(f"[{self.account_name}] 登录检查异常: {e}", exc_info=True)
        return False

    def get_supertopics_page(self, page=1):
        """获取指定页的超话列表
        
        Args:
            page (int): 页码，从1开始
            
        Returns:
            dict: API响应数据，失败返回None
        """
        url = f"https://weibo.com/ajax/profile/topicContent?tabid=231093_-_chaohua&page={page}"
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'https://weibo.com/u/page/follow/{self.account_uid}/231093_-_chaohua'
        }
        
        try:
            # 添加随机延迟避免请求过快
            delay = random.uniform(1, 3)
            self.logger.debug(f"[{self.account_name}] 获取第{page}页超话列表前等待 {delay:.1f}秒...")
            time.sleep(delay)
            
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
            
            # 检查响应内容
            if response.status_code != 200:
                self.logger.error(f"[{self.account_name}] 请求失败，状态码: {response.status_code}")
                return None
                
            try:
                data = response.json()
            except json.JSONDecodeError:
                self.logger.error(f"[{self.account_name}] 响应不是有效的JSON格式: {response.text}")
                return None
                
            if data.get('ok') != 1:
                self.logger.error(f"[{self.account_name}] API返回错误: {data}")
                return None
            
            return data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"[{self.account_name}] 获取第{page}页超话列表时网络错误: {str(e)}", exc_info=True)
        except Exception as e:
            self.logger.error(f"[{self.account_name}] 获取第{page}页超话列表时发生错误: {str(e)}", exc_info=True)
        return None

    def get_supertopics(self):
        """获取所有关注的超话列表（支持分页）"""
        all_topics = []
        current_page = 1
        max_page = 1
        
        self.logger.info(f"[{self.account_name}] 开始获取超话列表...")
        
        while current_page <= max_page:
            self.logger.info(f"[{self.account_name}] 正在获取第 {current_page} 页...")
            
            # 获取当前页数据
            data = self.get_supertopics_page(current_page)
            
            if not data:
                self.logger.error(f"[{self.account_name}] 获取第 {current_page} 页失败，停止获取")
                break
            
            # 获取分页信息
            page_info = data.get('data', {})
            max_page = page_info.get('max_page', 1)
            total_number = page_info.get('total_number', 0)
            
            self.logger.info(f"[{self.account_name}] 第 {current_page} 页获取成功，总页数: {max_page}，总超话数: {total_number}")
            
            # 解析当前页的超话数据
            topics_list = page_info.get('list', [])
            page_topics = []
            
            for topic_list in topics_list:
                # 只处理关注的超话
                if topic_list.get('following'):
                    # 从oid中提取容器ID
                    oid_parts = topic_list.get('oid', '').split(':')
                    containerid = oid_parts[-1] if len(oid_parts) > 1 else None
                    
                    if containerid:
                        page_topics.append({
                            'title': topic_list.get('title', ''),
                            'containerid': containerid,
                            'oid': topic_list.get('oid', ''),
                            'scheme': unquote(topic_list.get('scheme', ''))
                        })
            
            all_topics.extend(page_topics)
            self.logger.info(f"[{self.account_name}] 第 {current_page} 页获取到 {len(page_topics)} 个关注的超话")
            
            # 如果当前页没有数据或者已经到达最大页数，停止获取
            if not page_topics or current_page >= max_page:
                break
            
            # 继续获取下一页
            current_page += 1
        
        self.logger.info(f"[{self.account_name}] 超话列表获取完成，共 {len(all_topics)} 个关注的超话")
        return all_topics

    def save_topics(self, topics):
        """保存超话列表到文件"""
        try:
            with open(self.topics_file, 'w', encoding='utf-8') as f:
                json.dump(topics, f, ensure_ascii=False, indent=2)
            self.logger.info(f"[{self.account_name}] 超话列表已保存到 {self.topics_file}")
        except Exception as e:
            self.logger.error(f"[{self.account_name}] 保存超话列表时出错: {str(e)}", exc_info=True)

    def load_topics(self):
        """从文件加载超话列表"""
        try:
            if os.path.exists(self.topics_file):
                with open(self.topics_file, 'r', encoding='utf-8') as f:
                    topics = json.load(f)
                    self.logger.info(f"[{self.account_name}] 从文件加载 {len(topics)} 个超话")
                    return topics
            return None
        except Exception as e:
            self.logger.error(f"[{self.account_name}] 加载超话列表时出错: {str(e)}", exc_info=True)
            return None

    def sign_topic(self, topic):
        """执行超话签到"""
        checkin_url = "https://weibo.com/p/aj/general/button"

        topic_id = topic['containerid']
        topic_url = f"https://weibo.com/p/{topic_id}/super_index"
        
        # 构造签到请求参数
        params = {
            'ajwvr': '6',
            'api': 'http://i.huati.weibo.com/aj/super/checkin',
            'texta': '签到',
            'textb': '已签到',
            'status': '0',
            'id': topic_id,
            'location': 'page_极速版超话_super_index',
            'timezone': 'GMT+0800',
            'lang': 'zh-cn',
            'plat': 'Win32',
            'ua': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0',
            'screen': '1366*768',
            '__rnd': str(int(time.time() * 1000))
        }
        
        # 签到请求的Referer必须是超话页面
        headers = {
            'Referer': topic_url,  # 签到请求必须来自超话页面
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': '*/*'
        }
        
        try:
            # 随机延迟避免请求过快
            delay = random.uniform(15, 35)
            self.logger.debug(f"[{self.account_name}] 签到 {topic['title']} 前等待 {delay:.1f}秒...")
            time.sleep(delay)
            
            start_time = time.time()
            response = self.session.post(checkin_url, params=params, headers=headers)
            response.raise_for_status()
            elapsed = time.time() - start_time
            
            try:
                result = response.json()
            except json.JSONDecodeError:
                self.logger.error(f"[{self.account_name}] 签到响应不是有效的JSON: {response.text}")
                return False, "响应不是有效的JSON"
                
            if result.get('code') == '100000':
                self.logger.info(f"[{self.account_name}] 签到成功: {topic['title']} (耗时: {elapsed:.2f}秒)")
                return True, "签到成功"
            else:
                msg = result.get('msg', '未知错误')
                self.logger.warning(f"[{self.account_name}] 签到失败: {topic['title']}, 原因: {msg} (耗时: {elapsed:.2f}秒)")
                
                # 如果是重复签到，也视为成功
                if "已签到" in msg or "重复签到" in msg:
                    return True, msg
                    
                return False, msg
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"[{self.account_name}] 签到请求网络错误: {str(e)}", exc_info=True)
            return False, f"网络错误: {str(e)}"
        except Exception as e:
            self.logger.error(f"[{self.account_name}] 签到过程中发生错误: {str(e)}", exc_info=True)
            return False, f"系统错误: {str(e)}"
            
        return False, "未知错误"
    
    def save_sign_results(self):
        """保存签到结果到文件"""
        if not self.sign_results:
            return
            
        # 确保结果目录存在
        os.makedirs(RESULTS_DIR, exist_ok=True)
        
        # 创建文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sign_results_{self.account_name}_{timestamp}.json"
        filepath = os.path.join(RESULTS_DIR, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'account': self.account_name,
                    'timestamp': datetime.now().isoformat(),
                    'results': self.sign_results
                }, f, ensure_ascii=False, indent=2)
            self.logger.info(f"[{self.account_name}] 签到结果已保存到 {filepath}")
        except Exception as e:
            self.logger.error(f"[{self.account_name}] 保存签到结果时出错: {str(e)}", exc_info=True)
    
    def run_for_account(self, update_topics=False):
        """为单个账号执行签到流程
        
        Args:
            update_topics (bool): 是否强制更新超话列表
        """
        if not self.check_login():
            self.logger.error(f"[{self.account_name}] 登录状态检查失败，跳过该账号")
            return False
            
        # 获取超话列表逻辑
        topics = None
        
        # 1. 如果用户要求更新超话列表
        if update_topics:
            self.logger.info(f"[{self.account_name}] 用户要求更新超话列表，重新获取...")
            topics = self.get_supertopics()
            if topics:
                self.save_topics(topics)
        
        # 2. 尝试从文件加载超话列表
        if topics is None:
            topics = self.load_topics()
            
        # 3. 如果文件不存在或加载失败，重新获取
        if not topics:
            self.logger.warning(f"[{self.account_name}] 超话列表文件不存在或加载失败，重新获取...")
            topics = self.get_supertopics()
            if topics:
                self.save_topics(topics)
            
        if not topics:
            self.logger.error(f"[{self.account_name}] 无法获取超话列表，跳过该账号")
            return False
            
        # 执行签到
        self.logger.info(f"[{self.account_name}] 开始签到，共 {len(topics)} 个超话")
        success_count = 0
        
        for i, topic in enumerate(topics, 1):
            self.logger.info(f"[{self.account_name}] 签到进度: {i}/{len(topics)}")
            start_time = time.time()
            status, message = self.sign_topic(topic)
            elapsed = time.time() - start_time
            
            # 记录结果
            result = {
                'topic': topic['title'],
                'containerid': topic['containerid'],
                'status': 'success' if status else 'failed',
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'elapsed': elapsed
            }
            self.sign_results.append(result)
            
            if status:
                success_count += 1
        
        self.logger.info(f"[{self.account_name}] 签到完成! 成功: {success_count}/{len(topics)}")
        
        # 保存签到结果
        self.save_sign_results()
        return True

def setup_logging():
    """配置日志记录"""
    # 确保日志目录存在
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    # 创建主日志文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    main_log_file = os.path.join(LOGS_DIR, f"weibo_super_topic_{timestamp}.log")
    error_log_file = os.path.join(LOGS_DIR, f"weibo_super_topic_error_{timestamp}.log")
    
    # 创建主日志记录器
    logger = logging.getLogger('weibo_super_topic')
    logger.setLevel(logging.DEBUG)
    
    # 创建文件处理器 - 所有日志
    file_handler = logging.FileHandler(main_log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 创建错误文件处理器 - 只记录错误
    error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    error_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到主记录器
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)
    
    # 配置根记录器，避免重复日志
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)  # 设置较高的级别避免处理低级日志
    root_logger.addHandler(logging.NullHandler())  # 添加空处理器避免默认行为
    
    return logger

def load_accounts(logger):
    """加载多账号信息"""
    try:
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                accounts = json.load(f)
                logger.info(f"从 {ACCOUNTS_FILE} 加载了 {len(accounts)} 个账号")
                return accounts
        else:
            logger.error(f"账号文件 {ACCOUNTS_FILE} 不存在")
            return []
    except Exception as e:
        logger.error(f"加载账号信息时出错: {str(e)}", exc_info=True)
        return []

def list_accounts(accounts, logger):
    """列出所有账号名称"""
    logger.info("\n可用的微博账号:")
    logger.info("-" * 40)
    for idx, account in enumerate(accounts, 1):
        name = account.get('name', f"未命名账号{idx}")
        logger.info(f"{idx}. {name}")
    logger.info("-" * 40)

def main():
    """主函数，处理多账号签到"""
    # 设置日志记录
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info(f"微博超话签到脚本启动 (支持分页获取) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    # 设置命令行参数
    parser = argparse.ArgumentParser(description='微博超话签到脚本 (支持分页获取完整超话列表)')
    parser.add_argument('-a', '--account', type=str, help='指定要签到的账号名称')
    parser.add_argument('-l', '--list', action='store_true', help='列出所有账号名称')
    parser.add_argument('-u', '--update-topics', action='store_true', 
                        help='强制更新超话列表（默认使用本地保存的列表）')
    args = parser.parse_args()
    
    # 加载账号信息
    accounts = load_accounts(logger)
    if not accounts:
        logger.error("没有可用的账号信息，请检查配置文件")
        return
    
    # 列出账号选项
    if args.list:
        list_accounts(accounts, logger)
        return
    
    # 处理账号过滤
    if args.account:
        # 查找匹配的账号
        matched_accounts = [acc for acc in accounts if acc.get('name', '').lower() == args.account.lower()]
        
        if not matched_accounts:
            logger.error(f"未找到账号: {args.account}")
            logger.info("可用的账号列表:")
            list_accounts(accounts, logger)
            return
            
        accounts_to_process = matched_accounts
        logger.info(f"将处理账号: {args.account}")
    else:
        accounts_to_process = accounts
        logger.info(f"将处理所有 {len(accounts)} 个账号")
    
    # 显示更新选项状态
    if args.update_topics:
        logger.info("已启用强制更新超话列表选项")
    else:
        logger.info("将使用本地保存的超话列表（如存在）")
    
    total_accounts = len(accounts_to_process)
    success_accounts = 0
    
    for idx, account in enumerate(accounts_to_process, 1):
        account_name = account.get('name', f"账号{idx}")
        cookies = account.get('cookies', {})
        account_uid = account.get('uid')
        
        logger.info(f"\n{'='*50}")
        logger.info(f"处理账号: {account_name} ({idx}/{total_accounts})")
        logger.info(f"{'='*50}")
        
        # 为每个账号使用主日志记录器
        signer = WeiboSuperTopicSigner(account_name, logger, account_uid)
        if signer.load_cookies(cookies):
            if signer.run_for_account(update_topics=args.update_topics):
                success_accounts += 1
        
        # 账号间延迟
        if idx < total_accounts:
            delay = random.uniform(60, 90)
            logger.info(f"\n等待 {delay:.1f}秒后处理下一个账号...")
            time.sleep(delay)
    
    logger.info(f"\n所有账号处理完成! 成功: {success_accounts}/{total_accounts}")
    logger.info("=" * 60)
    logger.info(f"脚本运行结束 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

if __name__ == "__main__":

    main()
