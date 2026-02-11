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

# --- 管理员核心功能区 ---
def delete_post(index):
    """删除帖子"""
    conn = get_connection()
    df = get_data("posts")
    df = df.drop(index)
    conn.update(worksheet="posts", data=df)

def update_post_full(index, new_content, new_filename=None, new_file_link=None):
    """同时更新内容和文件"""
    conn = get_connection()
    df = get_data("posts")
    
    # 1. 更新文字
    df.at[index, "content"] = new_content
    
    # 2. 如果传了新文件，更新文件信息
    if new_file_link and new_filename:
        df.at[index, "filename"] = new_filename
        df.at[index, "file_link"] = new_file_link
        
    conn.update(worksheet="posts", data=df)

def get_config(key, default):
    df = get_data("config")
    if df.empty: return default
    res = df[df['key'] == key]
    return res.iloc[0]['value'] if not res.empty else default

def update_config_cloud(key, value):
    conn = get_connection()
    df = get_data("config")
    if key in df['key'].values:
        df.loc[df['key'] == key, 'value'] = value
    else:
        new_row = pd.DataFrame([{"key": key, "value": value}])
        df = pd.concat([df, new_row], ignore_index=True)
    conn.update(worksheet="config", data=df)

# --- 4. 页面显示 ---
def apply_style():
    st.markdown("""
    <style>
    .stApp {background: #f8fafc; font-family: 'Helvetica', sans-serif;}
    .hero {
        background: linear-gradient(135deg, #1e3a8a, #172554); 
        color: white; padding: 80px 20px; text-align: center; border-radius: 0 0 50px 50px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.2); margin-bottom: 40px;
    }
    .hero h1 { font-family: 'Times New Roman', serif; font-size: 4em; font-weight: 700; text-shadow: 0 4px 10px rgba(0,0,0,0.3); margin-bottom: 10px; }
    .card {
        background: white; padding: 25px; border-radius: 15px; border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 20px;
    }
    .download-btn {
        display: inline-block; padding: 6px 12px; background-color: #eff6ff; 
        color: #2563eb; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 0.85em;
        border: 1px solid #dbeafe; margin-top: 10px;
    }
    .download-btn:hover { background-color: #dbeafe; }
    </style>
    """, unsafe_allow_html=True)

def main():
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False

    apply_style()
    
    announcement = get_config("announcement", "Ph.D. Nexus - Global Research Hub")
    
    st.markdown(f"""
    <div class="hero">
        <h1>Ph.D. NEXUS</h1>
        <p style="font-size: 1.4em; opacity: 0.9; font-weight: 300;">Connecting Intelligence, Sharing Knowledge.</p>
        <div style="margin-top: 30px; display: inline-block; background: rgba(255,255,255,0.15); padding: 8px 20px; border-radius: 30px; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2);">
            📢 {announcement}
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🏛️ 学术大厅 (Forum)", "📈 数据洞察 (Insights)", "⚙️ 管理控制台 (Admin)"])
    
    # --- Tab 1: 论坛 ---
    with tab1:
        c1, c2 = st.columns([7, 3])
        
        # 发布区
        with c2:
            st.markdown("### 📤 发布成果 (Publish)")
            with st.container(border=True):
                with st.form("new_post"):
                    u_name = st.text_input("Name / ID")
                    u_cat = st.selectbox("Category", ["Computer Science", "Biology", "Physics", "Humanities"])
                    u_text = st.text_area("Abstract / Description")
                    u_file = st.file_uploader("Attachment", type=['pdf', 'zip', 'py', 'docx', 'png', 'jpg'])
                    
                    if st.form_submit_button("🚀 Submit to Nexus"):
                        if u_name and u_text:
                            if save_post_final(u_name, u_text, u_cat, u_file):
                                st.success("发布成功！")
                                time.sleep(1)
                                st.rerun()
        
        # 展示区 (含管理员功能)
        with c1:
            st.markdown("### 📚 最新文献 (Latest Papers)")
            df = get_data("posts")
            if not df.empty:
                df = df.sort_index(ascending=False)
                for i, row in df.iterrows():
                    dl_html = ""
                    if row['file_link']:
                        dl_html = f'<a href="{row["file_link"]}" target="_blank" class="download-btn">📥 Download: {row["filename"]}</a>'
                    
                    avatar = f"https://api.dicebear.com/9.x/initials/svg?seed={row['avatar_seed']}"
                    
                    col_icon, col_content = st.columns([1, 8])
                    with col_icon:
                        st.image(avatar, width=50)
                    with col_content:
                        st.markdown(f"""
                        <div class="card">
                            <div style="color: #64748b; font-size: 0.8em; margin-bottom: 8px;">
                                <span style="color:#94a3b8">#{i}</span> {row['time']} • <span style="background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:10px;">{row['category']}</span>
                            </div>
                            <h3 style="margin: 0 0 10px 0; color: #0f172a;">{row['username']}</h3>
                            <p style="color: #334155; line-height: 1.6;">{row['content']}</p>
                            {dl_html}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 点赞
                        c_like, c_admin_area = st.columns([2, 8])
                        with c_like:
                            if st.button(f"👍 ({row['likes']})", key=f"btn_{i}"):
                                update_likes(i, row['likes'])
                                st.rerun()

                        # --- 管理员操作面板 (升级版) ---
                        if st.session_state.is_admin:
                            with st.expander(f"🔴 管理员操作 (#{i})"):
                                st.caption("提示：如果不上传新文件，则原文件保持不变。")
                                
                                # 1. 编辑文字
                                new_text = st.text_area("修正内容", value=row['content'], key=f"edit_text_{i}")
                                
                                # 2. 编辑文件 (新增)
                                new_file = st.file_uploader("更换附件 (可选)", type=['pdf', 'zip', 'py', 'docx', 'png'], key=f"edit_file_{i}")
                                
                                # 保存按钮
                                if st.button("💾 保存所有修改", key=f"save_{i}"):
                                    final_link = None
                                    final_name = None
                                    
                                    # 如果管理员传了新文件，就上传
                                    if new_file:
                                        with st.spinner("正在替换旧文件..."):
                                            final_link = upload_to_cloud(new_file)
                                            final_name = new_file.name
                                    
                                    # 更新数据库
                                    update_post_full(i, new_text, final_name, final_link)
                                    st.success("帖子内容与文件已更新！")
                                    time.sleep(1)
                                    st.rerun()
                                
                                st.markdown("---")
                                if st.button("🗑️ 永久删除", key=f"del_{i}", type="primary"):
                                    delete_post(i)
                                    st.error("已删除！")
                                    time.sleep(1)
                                    st.rerun()

    # --- Tab 2: 洞察 ---
    with tab2:
        df = get_data("posts")
        if not df.empty:
            st.metric("Total Papers", len(df))
            st.bar_chart(df['category'].value_counts())

    # --- Tab 3: 管理登录 ---
    with tab3:
        if not st.session_state.is_admin:
            pwd = st.text_input("Admin Token", type="password")
            if st.button("Login"):
                if pwd == "phd2024":
                    st.session_state.is_admin = True
                    st.rerun()
        else:
            st.success("✅ 管理员已登录")
            with st.form("global_config"):
                new_ann = st.text_input("更新全站公告", announcement)
                if st.form_submit_button("更新公告"):
                    update_config_cloud("announcement", new_ann)
                    st.success("公告已更新")
                    st.rerun()
            
            if st.button("退出登录"):
                st.session_state.is_admin = False
                st.rerun()

if __name__ == "__main__":
    main()
