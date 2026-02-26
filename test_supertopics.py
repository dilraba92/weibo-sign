"""
超话获取测试Demo
用于测试WeiboSuperTopicSigner类的超话获取功能
"""

import json
import logging
import os
from main import WeiboSuperTopicSigner, load_accounts, setup_logging

def test_get_supertopics():
    """测试获取超话列表功能"""
    
    # 设置日志
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("超话获取测试Demo启动")
    logger.info("=" * 60)
    
    # 加载账号信息
    accounts = load_accounts(logger)
    if not accounts:
        logger.error("没有可用的账号信息，请检查配置文件")
        return
    
    # 使用第一个账号进行测试
    account = accounts[0]
    account_name = account.get('name', 'test_account')
    cookies = account.get('cookies', {})
    account_uid = account.get('uid')
    
    logger.info(f"\n使用账号进行测试: {account_name}")
    logger.info(f"账号UID: {account_uid}")
    
    # 创建签到器实例
    signer = WeiboSuperTopicSigner(account_name, logger, account_uid)
    
    # 加载cookies
    if not signer.load_cookies(cookies):
        logger.error("加载cookies失败，测试终止")
        return
    
    # 检查登录状态
    logger.info("\n检查登录状态...")
    if not signer.check_login():
        logger.error("登录状态检查失败，请检查cookies是否有效")
        return
    
    logger.info("登录状态检查通过 ✓")
    
    # 获取超话列表
    logger.info("\n开始获取超话列表...")
    topics = signer.get_supertopics()
    
    if not topics:
        logger.error("获取超话列表失败")
        return
    
    # 显示获取到的超话信息
    logger.info(f"\n成功获取 {len(topics)} 个超话:")
    logger.info("-" * 80)
    
    for idx, topic in enumerate(topics, 1):
        logger.info(f"\n【超话 {idx}】")
        logger.info(f"  名称: {topic.get('title', 'N/A')}")
        logger.info(f"  容器ID: {topic.get('containerid', 'N/A')}")
        logger.info(f"  OID: {topic.get('oid', 'N/A')}")
        logger.info(f"  Scheme: {topic.get('scheme', 'N/A')}")
    
    logger.info("\n" + "-" * 80)
    
    # 保存超话列表到文件
    signer.save_topics(topics)
    logger.info(f"\n超话列表已保存到: {signer.topics_file}")
    
    # 测试从文件加载超话列表
    logger.info("\n测试从文件加载超话列表...")
    loaded_topics = signer.load_topics()
    
    if loaded_topics:
        logger.info(f"成功从文件加载 {len(loaded_topics)} 个超话 ✓")
        
        # 验证数据一致性
        if len(loaded_topics) == len(topics):
            logger.info("数据一致性验证通过 ✓")
        else:
            logger.warning("数据一致性验证失败: 数量不匹配")
    else:
        logger.error("从文件加载超话列表失败")
    
    logger.info("\n" + "=" * 60)
    logger.info("测试完成!")
    logger.info("=" * 60)

if __name__ == "__main__":
    test_get_supertopics()