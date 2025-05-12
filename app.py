import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import config
from datetime import datetime
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
import xlsxwriter
from io import BytesIO
import traceback
import logging
import logging.handlers
import sys
from functools import wraps

# 在文件开头的导入语句之后，但在路由定义之前添加装饰器定义
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
                            'data': data,  # 添加请求数据
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
                        print(f"Log recorded: {action_type} - {module_name}")  # 调试信息

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

# 修改日志配置函数
def setup_logging():
    try:
        # 在用户主目录下创建日志目录
        home_dir = os.path.expanduser('~')  # 获取用户主目录
        log_dir = os.path.join(home_dir, 'cost_server_logs')
        os.makedirs(log_dir, exist_ok=True)

        log_file = os.path.join(log_dir, 'flask_app.log')

        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10000000, backupCount=5)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))

        # 确保移除任何现有的处理程序
        for hdlr in app.logger.handlers[:]:
            app.logger.removeHandler(hdlr)

        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Flask app startup')

    except Exception as e:
        print(f"Error setting up logging: {str(e)}")

def get_db_connection():
    conn = mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        passwd=config.DB_PASS,
        database=config.DB_NAME,
        autocommit=True
    )
    return conn

@app.route('/')
def index():
    if 'username' in session:
        return render_template('homepage.html', has_log_access=has_log_access)
    else:
        return redirect(url_for('login'))

@app.route('/enter_data', methods=['GET', 'POST'])
@log_user_action('数据录入', '数据管理')
def enter_data():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        project_id = request.form.get('project_id')
        version_id = request.form.get('version_id')
        action = request.form.get('action')

        if not project_id or not version_id:
            flash('请选择项目和版本')
            return redirect(url_for('enter_data'))

        if action == "添加楼宇|构筑物信息":
            return redirect(url_for('add_building', project_id=project_id, version_id=version_id))
        elif action == "录入成本数据":
            return redirect(url_for('enter_unit_indicator', project_id=project_id, version_id=version_id))

    # 获取所有项目
    cursor.execute("SELECT project_id, project_name FROM projects")
    projects = cursor.fetchall()

    # 获取所有版本
    cursor.execute("SELECT version_id, version_name FROM versions")
    versions = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('enter_data.html', projects=projects, versions=versions)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            log_system_event(username, "登录系统", "用户管理", f"用户 {username} 成功登录系统")
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误')
            return redirect(url_for('login'))
            
        cursor.close()
        conn.close()
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'username' in session:
        username = session['username']
        log_system_event(username, "退出系统", "用户管理", f"用户 {username} 退出系统")
        session.pop('username', None)
    return redirect(url_for('login'))

def has_log_access(username):
    # 检查用户是否有权查看日志
    if username == 'admin':
        return True
    return False

def log_system_event(username, action_type, module_name, event_detail):
    # 记录系统事件
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取客户端IP
        ip_address = request.remote_addr
        if request.headers.getlist("X-Forwarded-For"):
            ip_address = request.headers.getlist("X-Forwarded-For")[0]
        
        cursor.execute("""
            INSERT INTO user_logs
            (username, access_time, ip_address, action_type, action_detail, module_name)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            username,
            datetime.now(),
            ip_address,
            action_type,
            event_detail,
            module_name
        ))
        
        conn.commit()
    except Exception as e:
        print(f"Error logging system event: {str(e)}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    setup_logging()
    app.run(debug=True, host='0.0.0.0')