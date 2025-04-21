import gradio as gr
import requests
import json
from urllib.parse import quote
import os
from datetime import datetime
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
import sys
import threading
from urllib.error import URLError
import socket

# 配置日志
def setup_logger():
    logger = logging.getLogger('unifuncs_reader')
    logger.setLevel(logging.DEBUG)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '\n%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # 添加处理器到日志记录器
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()

def create_session_with_retry():
    session = requests.Session()
    # 设置更强大的重试策略
    retries = Retry(
        total=5,  # 增加到5次重试
        backoff_factor=2,  # 增加退避因子，使重试间隔更长
        status_forcelist=[500, 502, 503, 504],  # 需要重试的状态码
        allowed_methods=["GET", "POST"],  # 允许重试的方法
        respect_retry_after_header=True  # 尊重服务器的Retry-After头
    )
    # 将重试策略应用到会话
    adapter = HTTPAdapter(max_retries=retries, pool_maxsize=10, pool_connections=5)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def save_result(url, content, format_type):
    # 创建保存目录
    save_dir = "saved_results"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_url = "".join(c if c.isalnum() else "_" for c in url[:30])
    filename = f"{safe_url}_{timestamp}.{format_type}"
    filepath = os.path.join(save_dir, filename)
    
    # 保存内容
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    
    logger.info(f"结果已保存到: {filepath}")
    return filepath

def handle_error_response(response):
    """处理错误响应"""
    try:
        error_data = response.json()
        if isinstance(error_data, dict):
            error_code = error_data.get('code')
            error_message = error_data.get('message', '未知错误')
            request_id = error_data.get('requestId', '无')
            
            error_details = f"""
错误详情：
- 错误代码：{error_code}
- 错误信息：{error_message}
- 请求ID：{request_id}
- 状态码：{response.status_code}

可能的解决方案：
1. 如果是服务器错误(-20001或502)，请稍后重试
2. 检查API密钥是否正确
3. 确认URL是否可访问
4. 检查网络连接是否正常
"""
            # 在终端打印详细错误信息
            logger.error(f"API请求失败:\n{error_details}")
            return error_details
    except:
        error_msg = f"请求失败: HTTP {response.status_code}\n{response.text}"
        logger.error(error_msg)
        return error_msg

def make_request_with_backoff(session, method, url, **kwargs):
    """带指数退避的请求函数"""
    max_retries = 5
    base_delay = 2  # 基础延迟（秒）
    
    for attempt in range(max_retries):
        try:
            if method.upper() == 'GET':
                response = session.get(url, **kwargs)
            else:
                response = session.post(url, **kwargs)
                
            # 检查是否需要重试的状态码
            if response.status_code in [500, 502, 503, 504]:
                raise requests.exceptions.RequestException(f"服务器返回错误状态码: {response.status_code}")
                
            return response
            
        except (requests.exceptions.RequestException, URLError, socket.error) as e:
            logger.warning(f"请求失败（尝试 {attempt+1}/{max_retries}）: {str(e)}")
            
            if attempt == max_retries - 1:
                # 最后一次尝试，重新抛出异常
                raise
                
            # 计算退避时间（带随机因子）
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            logger.info(f"等待 {delay:.2f} 秒后重试...")
            time.sleep(delay)

def web_reader(url, api_key, request_type, format_type="markdown", 
               include_images=True, include_videos=False, include_position=False,
               only_css_selectors="", wait_for_css_selectors="", exclude_css_selectors="",
               link_summary=False, progress=gr.Progress()):
    try:
        logger.info(f"开始处理URL: {url}")
        logger.info(f"请求类型: {request_type}")
        
        progress(0, desc="准备请求...")
        # 创建带重试机制的会话
        session = create_session_with_retry()
        
        # 处理CSS选择器
        only_css = [s.strip() for s in only_css_selectors.split(',')] if only_css_selectors else []
        wait_css = [s.strip() for s in wait_for_css_selectors.split(',')] if wait_for_css_selectors else []
        exclude_css = [s.strip() for s in exclude_css_selectors.split(',')] if exclude_css_selectors else []

        logger.debug(f"CSS选择器配置:")
        logger.debug(f"- 仅包含: {only_css}")
        logger.debug(f"- 等待: {wait_css}")
        logger.debug(f"- 排除: {exclude_css}")

        progress(0.2, desc="处理请求参数...")
        if request_type == "GET":
            # URL编码
            encoded_url = quote(url, safe='')
            # 构建GET请求URL
            base_url = f"https://api.unifuncs.com/api/web-reader/{encoded_url}"
            params = {
                "apiKey": api_key,
                "format": format_type,
                "includeImages": str(include_images).lower(),  # 转换为字符串
                "includeVideos": str(include_videos).lower(),
                "includePosition": str(include_position).lower(),
                "onlyCSSSelectors": ','.join(only_css) if only_css else None,
                "waitForCSSSelectors": ','.join(wait_css) if wait_css else None,
                "excludeCSSSelectors": ','.join(exclude_css) if exclude_css else None,
                "linkSummary": str(link_summary).lower()
            }
            logger.info("发送GET请求...")
            progress(0.4, desc="发送GET请求...")
            try:
                # 使用自定义退避重试函数
                response = make_request_with_backoff(
                    session, 
                    'GET', 
                    base_url, 
                    params=params, 
                    timeout=60,  # 增加超时时间
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                )
            except Exception as e:
                logger.error(f"GET请求失败: {str(e)}")
                raise
        else:  # POST请求
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            data = {
                "url": url,
                "format": format_type,
                "includeImages": include_images,
                "includeVideos": include_videos,
                "includePosition": include_position,
                "onlyCSSSelectors": only_css,
                "waitForCSSSelectors": wait_css,
                "excludeCSSSelectors": exclude_css,
                "linkSummary": link_summary
            }
            logger.info("发送POST请求...")
            progress(0.4, desc="发送POST请求...")
            try:
                # 使用自定义退避重试函数
                response = make_request_with_backoff(
                    session, 
                    'POST', 
                    "https://api.unifuncs.com/api/web-reader/read",
                    headers=headers,
                    json=data,
                    timeout=60  # 增加超时时间
                )
            except Exception as e:
                logger.error(f"POST请求失败: {str(e)}")
                raise

        logger.info(f"收到响应: HTTP {response.status_code}")
        progress(0.6, desc="处理响应...")
        
        # 检查是否为JSON错误响应
        is_error_json = False
        try:
            result = response.json()
            if isinstance(result, dict) and result.get('code') and result.get('code') < 0:
                is_error_json = True
                progress(1.0, desc="处理错误响应...")
                return handle_error_response(response)
        except json.JSONDecodeError:
            # 不是JSON格式，继续处理
            pass
            
        if response.status_code == 200 and not is_error_json:
            content = response.text
            progress(0.8, desc="保存结果...")
            
            # 保存结果
            saved_path = save_result(url, content, format_type)
            
            progress(1.0, desc="完成！")
            logger.info("处理完成")
            return f"结果已保存到: {saved_path}\n\n{content}"
        else:
            progress(1.0, desc="请求失败")
            return handle_error_response(response)

    except requests.exceptions.Timeout:
        error_msg = "请求超时，请稍后重试或检查网络连接"
        logger.error(error_msg)
        progress(1.0, desc="请求超时")
        return error_msg
    except requests.exceptions.ConnectionError:
        error_msg = "网络连接错误，请检查网络连接是否正常"
        logger.error(error_msg)
        progress(1.0, desc="连接错误")
        return error_msg
    except requests.exceptions.RequestException as e:
        error_msg = f"请求异常: {str(e)}"
        logger.error(error_msg)
        progress(1.0, desc="请求异常")
        if "502" in str(e):
            return "服务器暂时不可用(502错误)，这通常是临时性问题。请稍后再试或尝试不同的URL。"
        return error_msg
    except Exception as e:
        error_msg = f"发生错误: {str(e)}"
        logger.error(error_msg, exc_info=True)  # 打印完整的错误堆栈
        progress(1.0, desc="发生错误")
        return error_msg

# 创建Gradio界面
with gr.Blocks(title="网页内容提取工具", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # 网页内容提取工具
    基于unifuncs Reader API的网页内容提取工具，支持多种格式输出和自定义选项。
    结果将自动保存在 saved_results 目录下。
    
    注意事项：
    1. 如果遇到服务器错误(如502)，系统会自动重试
    2. 每个请求默认超时时间为60秒
    3. 如果持续失败，请尝试以下方法:
       - 稍后再试
       - 使用不同的URL
       - 检查API密钥是否正确
       - 检查网络连接
    4. 详细的错误信息会打印在终端中
    """)
    
    with gr.Row():
        with gr.Column():
            url_input = gr.Textbox(label="网页URL", placeholder="请输入要提取内容的网页URL")
            api_key = gr.Textbox(label="API Key", placeholder="请输入您的API Key", type="password")
            request_type = gr.Radio(choices=["GET", "POST"], label="请求类型", value="GET")
            format_type = gr.Dropdown(
                choices=["markdown", "md", "text", "txt", "json"],
                label="输出格式",
                value="markdown"
            )
            
            with gr.Row():
                include_images = gr.Checkbox(label="包含图片", value=True)
                include_videos = gr.Checkbox(label="包含视频", value=False)
                include_position = gr.Checkbox(label="包含位置信息", value=False)
                link_summary = gr.Checkbox(label="包含链接摘要", value=False)
            
            only_css_selectors = gr.Textbox(
                label="仅包含CSS选择器",
                placeholder="用逗号分隔多个选择器，如：article,.rich_media_content"
            )
            wait_for_css_selectors = gr.Textbox(
                label="等待CSS选择器",
                placeholder="用逗号分隔多个选择器"
            )
            exclude_css_selectors = gr.Textbox(
                label="排除CSS选择器",
                placeholder="用逗号分隔多个选择器"
            )
            
            submit_btn = gr.Button("提取内容", variant="primary")
            
        with gr.Column():
            output = gr.Textbox(label="提取结果", lines=20)
            
    submit_btn.click(
        web_reader,
        inputs=[
            url_input, api_key, request_type, format_type,
            include_images, include_videos, include_position,
            only_css_selectors, wait_for_css_selectors, exclude_css_selectors,
            link_summary
        ],
        outputs=output
    )

if __name__ == "__main__":
    logger.info("启动网页内容提取工具...")
    # 禁用共享链接，避免frpc相关问题
    demo.launch(share=False) 