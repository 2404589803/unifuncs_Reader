# 网页内容提取工具

这是一个基于 unifuncs Reader API 的网页内容提取工具，使用 Gradio 构建的用户界面，支持多种格式输出和自定义选项。

## 功能特点

- 支持 GET 和 POST 两种请求方式
- 多种输出格式：Markdown、纯文本、JSON
- 可自定义内容提取选项：
  - 是否包含图片
  - 是否包含视频
  - 是否包含位置信息
  - 是否包含链接摘要
- 支持 CSS 选择器过滤：
  - 仅包含特定元素
  - 等待特定元素加载
  - 排除特定元素

## 安装说明

1. 克隆项目到本地
2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 使用方法

1. 运行应用：
```bash
python app.py
```

2. 在浏览器中打开显示的本地URL（通常是 http://127.0.0.1:7860）

3. 在界面中输入：
   - 目标网页URL
   - API Key
   - 选择请求类型（GET/POST）
   - 配置其他可选参数
   - 点击"提取内容"按钮

## 注意事项

- 使用前需要获取 unifuncs Reader API 的 API Key
- CSS 选择器使用逗号分隔多个选择器
- 建议使用 Python 3.7 或更高版本 