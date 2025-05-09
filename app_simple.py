import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import config
from datetime import datetime
import logging
import sys
from functools import wraps

# 日志记录装饰器
def log_user_action(action_type, module_name=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # 先执行原始函数
                result = f(*args, **kwargs)

                # 只有当用户已登录时才记录日志
                if 'username' in session:
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()

                        # 获取客户端IP
                        if request.headers.getlist("X-Forwarded-For"):
                            ip_address = request.headers.getlist("X-Forwarded-For")[0]
                        else:
                            ip_address = request.remote_addr

                        # 获取更详细的操作信息
                        if request.method == 'POST':
                            if request.is_json:
                                data = request.json
                            else:
                                data = request.form.to_dict()
                        else:
                            data = request.args.to_dict()

                        # 构建更详细的action_detail
                        action_detail = {
                            'method': request.method,
                            'path': request.path,
                            'data': data,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }

                        # 获取操作对象的ID
                        data_id = None
                        if 'project_id' in kwargs:
                            data_id = kwargs['project_id']
                        elif 'building_id' in kwargs:
                            data_id = kwargs['building_id']
                        elif request.method == 'POST' and 'project_id' in data:
                            data_id = data['project_id']

                        # 插入日志记录
                        cursor.execute("""
                            INSERT INTO user_logs
                            (username, access_time, ip_address, action_type, action_detail, module_name, data_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            session['username'],
                            datetime.now(),
                            ip_address,
                            action_type,
                            str(action_detail),
                            module_name,
                            str(data_id) if data_id else None
                        ))

                        conn.commit()
                        print(f"Log recorded: {action_type} - {module_name}")

                    except Exception as e:
                        print(f"Error logging user action: {str(e)}")
                        if 'conn' in locals():
                            conn.rollback()
                    finally:
                        if 'cursor' in locals():
                            cursor.close()
                        if 'conn' in locals():
                            conn.close()

                return result
            except Exception as e:
                print(f"Error in decorated function: {str(e)}")
                raise

        return decorated_function
    return decorator

app = Flask(__name__)
app.secret_key = 'YOUR_SECRET_KEY'

# 确保文档目录存在
os.makedirs(os.path.join(app.static_folder, 'documents'), exist_ok=True)

# 数据库连接函数
def get_db_connection():
    conn = mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        passwd=config.DB_PASS,
        database=config.DB_NAME,
        autocommit=True
    )
    return conn

# 主页路由
@app.route('/')
def index():
    if 'username' in session:
        return render_template('homepage.html')
    else:
        return redirect(url_for('login'))

# 登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            session['role'] = user['role']
            session['last_activity'] = datetime.now().timestamp()
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误')
            
    return render_template('login.html')

# 登出路由
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 项目数据查询
@app.route('/query_data')
@log_user_action('查询数据', '数据查询')
def query_data():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    return render_template('query_data.html')

# API: 获取所有项目
@app.route('/get_all_projects', methods=['GET'])
def get_all_projects():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT p.*, v.version_name
            FROM projects p
            LEFT JOIN versions v ON p.version_id = v.version_id
            ORDER BY p.project_name
        """)
        
        projects = cursor.fetchall()
        
        # 转换日期对象为字符串
        for project in projects:
            if 'start_date' in project and project['start_date']:
                project['start_date'] = project['start_date'].strftime('%Y-%m-%d')
                
        cursor.close()
        conn.close()
        
        return jsonify({"success": True, "projects": projects})
    except Exception as e:
        print(f"Error in get_all_projects: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

# 启动应用
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)