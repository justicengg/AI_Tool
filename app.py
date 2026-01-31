import streamlit as st
import requests
from openai import OpenAI
import json
import pandas as pd
import os
import time
from bs4 import BeautifulSoup # <--- 新增这个库

# --- 页面配置 ---
st.set_page_config(page_title="AI Product Tool", layout="wide")
st.title("⚡️ Frontier AI - 全能提取助手")

if 'extracted_data' not in st.session_state:
    st.session_state['extracted_data'] = None

with st.sidebar:
    st.header("设置")
    api_key = st.text_input("DeepSeek/OpenAI API Key", type="password")
    base_url = st.text_input("Base URL", value="https://api.deepseek.com") 
    model_name = st.text_input("Model Name", value="deepseek-chat")

# --- 新增功能：提取图片和Logo ---
def get_meta_data(url):
    try:
        # 这里我们需要伪装成浏览器，不然有些网站不给图片
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. 尝试找 Open Graph 图片 (通常是最佳质量的封面图)
        og_image = soup.find("meta", property="og:image")
        image_url = og_image["content"] if og_image else ""
        
        # 2. 尝试找 Title
        page_title = soup.title.string if soup.title else ""
        
        # 3. 尝试找 Favicon (Logo)
        icon_link = soup.find("link", rel="icon")
        # 处理相对路径问题
        logo_url = icon_link["href"] if icon_link else ""
        if logo_url and not logo_url.startswith('http'):
            # 简单拼接一下，实际情况可能更复杂
            from urllib.parse import urljoin
            logo_url = urljoin(url, logo_url)
            
        return {
            "image_url": image_url,
            "logo_url": logo_url,
            "page_title": page_title
        }
    except Exception as e:
        return {"image_url": "", "logo_url": "", "page_title": ""}

# --- 原有的 Jina 抓取 ---
def get_web_content(url):
    jina_url = f"https://r.jina.ai/{url}"
    try:
        response = requests.get(jina_url, timeout=20)
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

# --- LLM 分析 ---
def analyze_content(content, client):
    prompt = """
    你是一个AI分析师。请分析网页内容(Markdown)，提取以下 JSON 字段：
    1. name (产品名)
    2. one_liner (一句话介绍)
    3. tags (标签列表，逗号分隔)
    4. pricing_type (Open Source, Freemium, Paid)
    5. cost_analysis (成本分析)
    6. deployment (部署简述)
    只返回纯 JSON 字符串。
    """
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": content[:20000]} 
            ],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"LLM Error: {str(e)}"

# --- 主逻辑 ---
target_url = st.text_input("输入产品链接 (GitHub / 官网)", placeholder="https://...")
start_btn = st.button("🚀 开始深度提取", type="primary")

if start_btn and api_key:
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    with st.status("正在全方位扫描...", expanded=True) as status:
        # 1. 并行：LLM分析文本 + Python抓取图片
        st.write("🔍 正在抓取网页元数据 (图片/Logo)...")
        meta_data = get_meta_data(target_url)
        
        st.write("📖 正在读取并理解内容 (LLM)...")
        raw_content = get_web_content(target_url)
        json_result = analyze_content(raw_content, client)
        
        try:
            clean_json = json_result.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json)
            
            # 【合并数据】把图片信息合并进去
            data['source_url'] = target_url
            data['hero_image'] = meta_data['image_url']
            data['logo_icon'] = meta_data['logo_url']
            
            st.session_state['extracted_data'] = data
            status.update(label="提取完成！", state="complete", expanded=False)
            
        except Exception as e:
            st.error(f"解析失败: {e}")

# --- 展示与保存 ---
if st.session_state['extracted_data']:
    data = st.session_state['extracted_data']
    
    # 展示图片效果
    col_img, col_info = st.columns([1, 2])
    with col_img:
        if data.get('hero_image'):
            st.image(data['hero_image'], caption="自动抓取的封面图")
        else:
            st.info("未找到封面图")
            
    with col_info:
        st.subheader(data.get('name'))
        st.write(data.get('one_liner'))
        st.json(data)

    # 保存按钮
    if st.button("💾 保存到 CSV"):
        csv_file = "ai_products_v2.csv" # 存个新文件
        # 处理列表转字符串
        if isinstance(data.get('tags'), list):
            data['tags'] = ", ".join(data['tags'])
            
        new_row = pd.DataFrame([data])
        if not os.path.isfile(csv_file):
            new_row.to_csv(csv_file, index=False, encoding='utf-8-sig')
        else:
            new_row.to_csv(csv_file, mode='a', header=False, index=False, encoding='utf-8-sig')
        st.toast("保存成功！包含图片链接！")