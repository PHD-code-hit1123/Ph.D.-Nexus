import streamlit as st
import plotly.express as px
import pandas as pd
import random
import time
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 引入 Cloudinary
import cloudinary
import cloudinary.uploader
import cloudinary.api

# --- 1. 全局配置 ---
st.set_page_config(
    page_title="Ph.D. Nexus | 旗舰版",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. Cloudinary 服务 ---
def init_cloudinary():
    c_config = st.secrets["cloudinary"]
    cloudinary.config(
        cloud_name=c_config["cloud_name"],
        api_key=c_config["api_key"],
        api_secret=c_config["api_secret"],
        secure=True
    )

def upload_to_cloud(uploaded_file):
    """上传函数 (防缓存+修复版)"""
    init_cloudinary()
    try:
        # 1. 强制 PDF 走 raw 模式
        res_type = "auto"
        if uploaded_file.name.lower().endswith(('.pdf', '.zip', '.docx', '.py', '.txt')):
            res_type = "raw"

        # 2. 上传 (传字节流 + unique_filename)
        response = cloudinary.uploader.upload(
            uploaded_file.getvalue(), 
            resource_type=res_type,   
            use_filename=True,        
            unique_filename=True      
        )
        return response['secure_url']
    except Exception as e:
        st.error(f"☁️ 上传服务报错: {e}")
        return None

# --- 3. 数据库连接 ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def get_data(worksheet_name):
    conn = get_connection()
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if worksheet_name == "posts":
            required = ["username", "content", "category", "time", "likes", "avatar_seed", "filename", "file_link"]
            if df.empty: return pd.DataFrame(columns=required)
            for col in required:
                if col not in df.columns: df[col] = None
        return df
    except:
        return pd.DataFrame()

def save_post_final(username, content, category, uploaded_file):
    conn = get_connection()
    df = get_data("posts")
    
    file_link = None
    file_name = None
    
    if uploaded_file:
        file_name = uploaded_file.name
        with st.spinner("🚀 正在上传文件到高速云端..."):
            file_link = upload_to_cloud(uploaded_file)
        if not file_link:
            st.error("❌ 文件上传失败")
            return False

    new_data = pd.DataFrame([{
        "username": username,
        "content": content,
        "category": category,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "likes": 0,
        "avatar_seed": str(random.randint(1000, 9999)),
        "filename": file_name,
        "file_link": file_link
    }])
    
    updated_df = pd.concat([df, new_data], ignore_index=True)
    conn.update(worksheet="posts", data=updated_df)
    return True

def update_likes(index, current_likes):
    conn = get_connection()
    df = get_data("posts")
    df.at[index, "likes"] = int(current_likes) + 1
    conn.update(worksheet="posts", data=df)

# --- 新增：管理员删除与编辑 ---
def delete_post(index):
    conn = get_connection()
    df = get_data("posts")
    df = df.drop(index)
    conn.update(worksheet="posts", data=df)

def edit_post_content(index, new_content):
    conn = get_connection()
    df = get_data("posts")
    df.at[index, "content"] = new_content
    conn.update(worksheet="posts", data=df)

def get_config(key, default):
    df = get_data("config")
    if df.empty: return default
    res = df[df['key']
