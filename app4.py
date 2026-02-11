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


# --- 2. Cloudinary 服务 (免费大文件存储) ---
def init_cloudinary():
    # 从 Secrets 读取配置
    c_config = st.secrets["cloudinary"]
    cloudinary.config(
        cloud_name=c_config["cloud_name"],
        api_key=c_config["api_key"],
        api_secret=c_config["api_secret"],
        secure=True
    )


def upload_to_cloud(uploaded_file):
    """上传函数 (防缓存版)：自动重命名 + 强制 RAW 模式"""
    init_cloudinary()
    try:
        # 1. 强制 PDF 走 raw 模式 (避开 401 权限问题)
        res_type = "auto"
        # 检查文件名后缀
        if uploaded_file.name.lower().endswith(('.pdf', '.zip', '.docx', '.py', '.txt')):
            res_type = "raw"

        # 2. 上传
        response = cloudinary.uploader.upload(
            uploaded_file.getvalue(), # 直接传字节数据，防止指针问题
            resource_type=res_type,   # 指定模式
            use_filename=True,        # 使用原文件名作为基础
            unique_filename=True      # <--- 关键！自动添加随机后缀，避开缓存！
        )
        return response['secure_url']
        
    except Exception as e:
        st.error(f"☁️ 上传服务报错: {e}")
        return None

# --- 3. 数据库连接 (Google Sheets) ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)


def get_data(worksheet_name):
    conn = get_connection()
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        # 确保列存在
        if worksheet_name == "posts":
            required = ["username", "content", "category", "time", "likes", "avatar_seed", "filename", "file_link"]
            if df.empty: return pd.DataFrame(columns=required)
            for col in required:
                if col not in df.columns: df[col] = None
        return df
    except:
        return pd.DataFrame()

# --- 新增：管理员删除与编辑功能 ---
def delete_post(index):
    """删除指定索引的帖子"""
    conn = get_connection()
    df = get_data("posts")
    # 也就是删除 DataFrame 里对应的这一行
    df = df.drop(index)
    conn.update(worksheet="posts", data=df)

def edit_post_content(index, new_content):
    """更新指定索引的帖子内容"""
    conn = get_connection()
    df = get_data("posts")
    # 修改指定单元格
    df.at[index, "content"] = new_content
    conn.update(worksheet="posts", data=df)


def save_post_final(username, content, category, uploaded_file):
    conn = get_connection()
    df = get_data("posts")

    file_link = None
    file_name = None

    # 1. 上传文件
    if uploaded_file:
        file_name = uploaded_file.name
        with st.spinner("🚀 正在上传文件到高速云端 (Cloudinary)..."):
            file_link = upload_to_cloud(uploaded_file)

        if not file_link:
            st.error("❌ 文件上传失败，请重试。")
            return False

    # 2. 存入表格
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


# --- 4. 视觉与页面 ---
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
        transition: transform 0.2s;
    }
    .card:hover { transform: translateY(-3px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
    .download-btn {
        display: inline-block; padding: 6px 12px; background-color: #eff6ff; 
        color: #2563eb; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 0.85em;
        border: 1px solid #dbeafe; margin-top: 10px;
    }
    .download-btn:hover { background-color: #dbeafe; }
    </style>
    """, unsafe_allow_html=True)


def main():
    apply_style()

    # 封面
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

        # 右侧发布栏
        with c2:
            st.markdown("### 📤 发布成果 (Publish)")
            with st.container(border=True):
                with st.form("new_post"):
                    u_name = st.text_input("Name / ID")
                    u_cat = st.selectbox("Category", ["Computer Science", "Biology", "Physics", "Humanities"])
                    u_text = st.text_area("Abstract / Description")
                    # 这里是 Cloudinary 上传器，支持大文件
                    u_file = st.file_uploader("Attachment (PDF/ZIP/Code)",
                                              type=['pdf', 'zip', 'py', 'docx', 'png', 'jpg'])

                    if st.form_submit_button("🚀 Submit to Nexus"):
                        if u_name and u_text:
                            if save_post_final(u_name, u_text, u_cat, u_file):
                                st.success("发布成功！文件已存入 Cloudinary。")
                                time.sleep(1)
                                st.rerun()

        # 左侧展示栏
        # 左侧展示栏 (修改版)
        with c1:
            st.markdown("### 📚 最新文献 (Latest Papers)")
            df = get_data("posts")
            if not df.empty:
                # 按索引倒序，保证新发的在上面，同时保留原始索引 i 用于删除
                df_sorted = df.sort_index(ascending=False)
                
                for i, row in df_sorted.iterrows():
                    # --- 1. 常规显示逻辑 ---
                    dl_html = ""
                    if row['file_link']:
                        # 判断是 Drive 还是 Base64 还是 Cloudinary
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
                        
                        # 常规用户点赞
                        c_like, c_admin = st.columns([2, 8])
                        with c_like:
                            if st.button(f"👍 ({row['likes']})", key=f"btn_{i}"):
                                update_likes(i, row['likes'])
                                st.rerun()

                        # --- 2. 管理员专属操作区 (核心升级) ---
                        # 只有登录后才会看到这个红色区域
                        if st.session_state.is_admin:
                            with st.expander(f"🔴 管理员操作 (操作对象: #{i})"):
                                st.warning("⚠️ 警告：修改直接同步至数据库，不可撤销。")
                                
                                # 编辑功能
                                new_text = st.text_area("修正内容", value=row['content'], key=f"edit_area_{i}")
                                if st.button("💾 保存修改", key=f"save_{i}"):
                                    edit_post_content(i, new_text)
                                    st.success("已更新！")
                                    time.sleep(1)
                                    st.rerun()
                                
                                st.markdown("---")
                                
                                # 删除功能
                                col_del1, col_del2 = st.columns([1, 1])
                                with col_del1:
                                    st.markdown("**危险区域:**")
                                with col_del2:
                                    if st.button("🗑️ 永久删除此贴", key=f"del_{i}", type="primary"):
                                        delete_post(i)
                                        st.error("帖子已从数据库移除。")
                                        time.sleep(1)
                                        st.rerun()

    # --- Tab 2: 洞察 ---
    with tab2:
        df = get_data("posts")
        if not df.empty:
            st.metric("Total Papers", len(df))
            # 简单的条形图
            st.bar_chart(df['category'].value_counts())
        else:
            st.info("No data yet.")

    # --- Tab 3: 管理 ---
    with tab3:
        if "is_admin" not in st.session_state: st.session_state.is_admin = False

        if not st.session_state.is_admin:
            pwd = st.text_input("Admin Token", type="password")
            if st.button("Login"):
                if pwd == "phd2024":
                    st.session_state.is_admin = True
                    st.rerun()
        else:
            st.success("Admin Logged In")
            with st.form("settings"):
                new_ann = st.text_input("Announcement", announcement)
                if st.form_submit_button("Update"):
                    update_config_cloud("announcement", new_ann)
                    st.success("Updated!")
                    st.rerun()


if __name__ == "__main__":

    main()




