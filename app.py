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

@app.route('/get_versions/<project_id>')
@log_user_action('查询版本信息', '版本管理')
def get_versions(project_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT v.version_id, v.version_name
        FROM versions v
        JOIN projects p ON p.version_id = v.version_id
        WHERE p.project_id = %s
    """, (project_id,))
    versions = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(versions=versions)

@app.route('/add_project', methods=['GET', 'POST'])
@log_user_action('添加项目', '项目管理')
def add_project():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        project_data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO projects (project_name, project_date, project_city, project_address,
                project_developer, project_CFA, project_count_area, project_land_area,
                project_green_area, project_outdoor_area, prj_type, version_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                project_data['project_name'], project_data['project_date'],
                project_data['project_city'], project_data['project_address'],
                project_data['project_developer'], float(project_data['project_CFA']),
                float(project_data['project_count_area']), float(project_data['project_land_area']),
                float(project_data['project_green_area']), float(project_data['project_outdoor_area']),
                project_data['prj_type'], int(project_data['version_id'])
            ))
            new_project_id = cursor.lastrowid

            # 调用存储过程更新成本指标基数
            cursor.callproc('compute_cost_categories', [new_project_id])
            conn.commit()
            return jsonify(success=True)
        except mysql.connector.Error as err:
            conn.rollback()
            return jsonify(success=False, message=str(err))
        finally:
            cursor.close()
            conn.close()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 获取所有项目信息
    cursor.execute('SELECT * FROM projects')
    projects = cursor.fetchall()

    # 获取版本信息
    cursor.execute('SELECT version_id, version_name FROM versions')
    versions = cursor.fetchall()
    versions_dict = {str(v['version_id']): v['version_name'] for v in versions}

    cursor.close()
    conn.close()

    return render_template('add_project.html', projects=projects, versions=versions, versions_dict=versions_dict)

@app.route('/add_building/<int:project_id>', methods=['GET', 'POST'])
@log_user_action('添加楼宇', '楼宇管理')
def add_building(project_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    version_id = request.args.get('version_id')  # 获取版本ID参数

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO buildings (project_id, building_name, public_facility, building_area,
                building_count_area, decorated_area, floors, floor_height, decoration_status,
                building_type, building_structure, version_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (project_id, data['building_name'], data['public_facility'], data['building_area'],
                  data['building_count_area'], data['decorated_area'], data['floors'], data['floor_height'],
                  data['decoration_status'], data['building_type'], data['building_structure'], data['version_id']
            ))
            conn.commit()
            new_building_id = cursor.lastrowid

            # 插入成功后，调用存储过程
            cursor.callproc('compute_cost_categories', [project_id])
            conn.commit()

            return jsonify(success=True, building_id=new_building_id)
        except mysql.connector.Error as err:
            conn.rollback()
            return jsonify(success=False, message=str(err))
        finally:
            cursor.close()
            conn.close()

    elif request.method == 'GET':
        cursor.execute("""
            SELECT b.building_id, b.project_id, b.building_name, b.public_facility, b.building_area, b.decorated_area,
                   b.building_count_area, b.floors, b.floor_height, b.decoration_status, b.building_type, b.building_structure, b.version_id, v.version_name
            FROM buildings b
            JOIN versions v ON b.version_id = v.version_id
            WHERE b.project_id = %s
        """, (project_id,))
        buildings = cursor.fetchall()
        print(f"Retrieved buildings data for project_id {project_id}: {buildings}")  # 调试输出

        cursor.execute("""
            SELECT v.version_id, v.version_name
            FROM versions v
            WHERE EXISTS (
                SELECT 1 FROM projects p WHERE p.project_id = %s
            )
        """, (project_id,))
        versions = cursor.fetchall()
        print(f"Retrieved versions data: {versions}")  # 调试输出

        versions_dict = {version['version_id']: version['version_name'] for version in versions}

        cursor.close()
        conn.close()

        return render_template('add_building.html', buildings=buildings, versions_dict=versions_dict, project_id=project_id, selected_version_id=version_id)


@app.route('/enter_unit_indicator/<int:project_id>', methods=['GET', 'POST'])
@log_user_action('成本指标录入', '数据管理')
def enter_unit_indicator(project_id):
    login_redirect = check_user_logged_in()
    if login_redirect:
        return login_redirect

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'GET':
        version_id = request.args.get('version_id')
        print(f"Entering enter_unit_indicator with project_id: {project_id}, version_id: {version_id}")

        cursor.execute("SELECT DISTINCT version_id, version_name FROM versions")
        versions = cursor.fetchall()

        if not versions:
            flash('没有到版本数据。')
            return redirect(url_for('enter_data'))

        version_id = version_id or versions[0]['version_id']

        cursor.execute("""
            SELECT category_id, category_name, parent_category_id, indicator_base_name, unit_indicator
            FROM cost_categories
            WHERE project_id = %s AND version_id = %s
        """, (project_id, version_id))
        all_categories = cursor.fetchall()

        def build_tree(categories, parent_id=None):
            tree = []
            for category in categories:
                if category['parent_category_id'] == parent_id:
                    children = build_tree(categories, category['category_id'])
                    if children:
                        category['children'] = children
                    tree.append(category)
            return tree

        categories_tree = build_tree(all_categories)

        return render_template('unit_indicator_form.html', categories=categories_tree, project_id=project_id, versions=versions, selected_version=version_id)

    elif request.method == 'POST':
        selected_version_id = request.form.get('version_id')

        unit_indicators = {key: value for key, value in request.form.items() if key.startswith('category_')}

        try:
            for category_id, unit_indicator in unit_indicators.items():
                cat_id = category_id.split('_')[1]
                if unit_indicator == '':
                    unit_indicator = None

                cursor.execute("""
                    UPDATE cost_categories SET unit_indicator = %s
                    WHERE category_id = %s AND project_id = %s AND version_id = %s
                """, (unit_indicator, cat_id, project_id, selected_version_id))

            conn.commit()

            return jsonify({'redirect': url_for('success_message')}), 200

        except mysql.connector.Error as err:
            conn.rollback()
            return jsonify({'message': '据保存失败'}), 500

        finally:
            cursor.close()
            conn.close()

@app.route('/update_building/<int:building_id>', methods=['POST'])
@log_user_action('更新楼宇', '楼宇管理')
def update_building(building_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    building_data = request.json
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  # 添加 dictionary=True 参数
    try:
        # 获取旧的楼宇名称
        cursor.execute("SELECT building_name FROM buildings WHERE building_id = %s", (building_id,))
        result = cursor.fetchone()
        old_building_name = result['building_name'] if result else None

        if old_building_name is None:
            return jsonify(success=False, message="Building not found"), 404

        # 更新 buildings 表
        cursor.execute("""
            UPDATE buildings
            SET building_name = %s, public_facility = %s, building_area = %s, building_count_area = %s, decorated_area = %s,
                floors = %s, floor_height = %s, decoration_status = %s, building_type = %s, building_structure = %s, version_id = %s
            WHERE building_id = %s
        """, (building_data['building_name'], building_data['public_facility'], building_data['building_area'],
              building_data['building_count_area'], building_data['decorated_area'], building_data['floors'],
              building_data['floor_height'], building_data['decoration_status'], building_data['building_type'],
              building_data['building_structure'], building_data['version_id'], building_id))

        # 更新 cost_categories 表
        cursor.execute("""
            UPDATE cost_categories
            SET category_name = %s
            WHERE project_id = %s AND category_name = %s
        """, (building_data['building_name'], building_data['project_id'], old_building_name))

        project_id = building_data['project_id']
        cursor.callproc('compute_cost_categories', [project_id])
        conn.commit()

        return jsonify(success=True)
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify(success=False, error=str(err))
    finally:
        cursor.close()
        conn.close()


@app.route('/update_building_name/<int:building_id>', methods=['POST'])
def update_building_name(building_id):
    data = request.json
    new_building_name = data.get('building_name')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE buildings
            SET building_name = %s
            WHERE building_id = %s
        """, (new_building_name, building_id))
        conn.commit()
        return jsonify(success=True)
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify(success=False, error=str(err)), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/save_building/<int:building_id>', methods=['POST'])
def save_building(building_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    data = request.json
    if not data:
        return jsonify(success=False, error="Invalid request data"), 400

    # 调试信息，记录接收到的数据
    print("Received save building data:", data)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        project_id = data.get('project_id')
        new_building_name = data.get('building_name')
        old_building_name = data.get('old_building_name')  # 获取旧的楼宇名称
        public_facility = bool(int(data.get('public_facility', 0)))  # 确保将字符转换为整数再转换为布尔值
        building_area = float(data.get('building_area', 0))
        decorated_area = float(data.get('decorated_area', 0))
        building_count_area = float(data.get('building_count_area', 0))
        floors = int(data.get('floors', 0))
        floor_height = float(data.get('floor_height', 0))
        decoration_status = data.get('decoration_status', '毛坯').strip()
        building_type = data.get('building_type', '').strip()
        building_structure = data.get('building_structure', '').strip()
        version_id = int(data.get('version_id', 0))

        # 检查必要数据是否存在
        if not all([new_building_name, building_area, building_type, building_structure, version_id]):
            print("Missing mandatory data:", [new_building_name, building_area, building_type, building_structure, version_id])
            return jsonify(success=False, error="Missing mandatory data"), 400

        # 更新数据库中的楼宇信息
        cursor.execute("""
            UPDATE buildings
            SET building_name = %s, public_facility = %s, building_area = %s, building_count_area = %s, decorated_area = %s,
                floors = %s, floor_height = %s, decoration_status = %s, building_type = %s, building_structure = %s, version_id = %s
            WHERE building_id = %s
        """, (new_building_name, public_facility, building_area, building_count_area, decorated_area, floors, floor_height,
              decoration_status, building_type, building_structure, version_id, building_id))

        # 更新 cost_categories 表
        cursor.execute("""
            UPDATE cost_categories
            SET category_name = %s
            WHERE project_id = %s AND category_name = %s
        """, (new_building_name, project_id, old_building_name))

        conn.commit()

        # 在此处返回更新后的数据，以便前端更新页面显示
        updated_building = {
            'building_id': building_id,
            'project_id': project_id,
            'building_name': new_building_name,
            'public_facility': public_facility,
            'building_area': building_area,
            'building_count_area': building_count_area,
            'decorated_area': decorated_area,
            'floors': floors,
            'floor_height': floor_height,
            'decoration_status': decoration_status,
            'building_type': building_type,
            'building_structure': building_structure,
            'version_id': version_id
        }

        return jsonify(success=True, **updated_building)
    except mysql.connector.Error as err:
        conn.rollback()
        # 输出数据库错误信息用于调试
        print(f"Database error: {err}")
        return jsonify(success=False, error=str(err))
    except Exception as e:
        # 输出其他错误信息用于调试
        print(f"Error processing request: {e}")
        return jsonify(success=False, error="Invalid request data"), 400
    finally:
        cursor.close()
        conn.close()


@app.route('/update_project', methods=['POST'])
@log_user_action('更新项目', '项目管理')
def update_project():
    project_data = request.json
    print("Received project data:", project_data)  # 添加日志

    try:
        project_id = project_data['project_id']
        project_name = project_data['project_name']
        project_date = project_data['project_date']
        project_city = project_data['project_city']
        project_address = project_data['project_address']
        project_developer = project_data['project_developer']
        project_CFA = float(project_data['project_CFA'])
        project_count_area = float(project_data['project_count_area'])
        project_land_area = float(project_data['project_land_area'])
        project_green_area = float(project_data['project_green_area'])
        project_outdoor_area = float(project_data['project_outdoor_area'])
        prj_type = project_data.get('prj_type')  # 新增字段
        version_id = int(project_data.get('version_id'))  # 确保转换为整数

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE projects
                SET project_name = %s, project_date = %s, project_city = %s, project_address = %s, project_developer = %s,
                    project_CFA = %s, project_count_area = %s, project_land_area = %s, project_green_area = %s,
                    project_outdoor_area = %s, prj_type = %s, version_id = %s
                WHERE project_id = %s
            """, (project_name, project_date, project_city, project_address, project_developer, project_CFA, project_count_area,
                  project_land_area, project_green_area, project_outdoor_area, prj_type, version_id, project_id))
            conn.commit()
            print(f"Project {project_id} updated successfully")  # 添加日志

            # 调用存储过程更新成本指标基数
            cursor.callproc('compute_cost_categories', [project_id])
            conn.commit()

            return jsonify(success=True)
        except mysql.connector.Error as err:
            conn.rollback()
            print(f"Database error: {err}")  # 添加日志
            return jsonify(success=False, error=str(err))
        finally:
            cursor.close()
            conn.close()
    except KeyError as e:
        print(f"Missing key in project data: {e}")  # 添加日志
        return jsonify(success=False, error=f"Missing key in project data: {e}")
    except ValueError as e:
        print(f"Invalid value in project data: {e}")  # 添加日志
        return jsonify(success=False, error=f"Invalid value in project data: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")  # 添加日志
        return jsonify(success=False, error=f"Unexpected error: {e}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    # 检查是否已经通过浏览器记住的凭据自动登录
    if 'username' not in session and request.authorization:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE username = %s", (request.authorization.username,))
            user = cursor.fetchone()
            if user and check_password_hash(user['password'], request.authorization.password):
                session['username'] = user['username']
                session['last_activity'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # 记录浏览器自动登录日志
                conn_log = get_db_connection()
                cursor_log = conn_log.cursor()
                try:
                    # 获取客户端IP
                    if request.headers.getlist("X-Forwarded-For"):
                        ip_address = request.headers.getlist("X-Forwarded-For")[0]
                    else:
                        ip_address = request.remote_addr

                    # 构建action_detail
                    action_detail = {
                        'method': request.method,
                        'path': request.path,
                        'event': '浏览器自动登录',
                        'user_agent': request.user_agent.string,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }

                    # 插入日志记录
                    cursor_log.execute("""
                        INSERT INTO user_logs
                        (username, access_time, ip_address, action_type, action_detail, module_name)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        user['username'],
                        datetime.now(),
                        ip_address,
                        '用户登录',
                        str(action_detail),
                        '用户管理'
                    ))
                    conn_log.commit()
                finally:
                    cursor_log.close()
                    conn_log.close()

                return redirect(url_for('index'))
        finally:
            cursor.close()
            conn.close()

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['username'] = username
            session['last_activity'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # 记录手动登录日志
            log_system_event(username, '用户登录', '用户管理', '手动登录')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误')
            # 记录登录失败日志
            log_system_event(username, '登录失败', '用户管理', '用户名或密码错误')

    return render_template('login.html')

# 修改会话检查函数
@app.before_request
def check_session():
    if 'username' in session:
        current_time = datetime.now()

        # 如果存在last_activity，检查是否超时
        if 'last_activity' in session:
            last_activity = datetime.strptime(session['last_activity'], '%Y-%m-%d %H:%M:%S')
            # 如果超过5分钟没��活动，记录退出日志
            if (current_time - last_activity).seconds > 300:  # 5分钟超时
                username = session['username']

                # 记录退出日志
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    # 获取客户端IP
                    if request.headers.getlist("X-Forwarded-For"):
                        ip_address = request.headers.getlist("X-Forwarded-For")[0]
                    else:
                        ip_address = request.remote_addr

                    # 构建action_detail
                    action_detail = {
                        'method': request.method,
                        'path': request.path,
                        'event': '会话超时退出（浏览器关闭）',
                        'user_agent': request.user_agent.string,
                        'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
                    }

                    # 插入退出日志
                    cursor.execute("""
                        INSERT INTO user_logs
                        (username, access_time, ip_address, action_type, action_detail, module_name)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        username,
                        current_time,
                        ip_address,
                        '用户退出',
                        str(action_detail),
                        '用户管理'
                    ))
                    conn.commit()
                finally:
                    cursor.close()
                    conn.close()

                session.clear()
                return redirect(url_for('login'))

        # 更新最后活动时间
        session['last_activity'] = current_time.strftime('%Y-%m-%d %H:%M:%S')

# 添加系统事件日志记录函数
def log_system_event(username, action_type, module_name, event_detail):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取客户端IP
        if request.headers.getlist("X-Forwarded-For"):
            ip_address = request.headers.getlist("X-Forwarded-For")[0]
        else:
            ip_address = request.remote_addr

        # 构建action_detail
        action_detail = {
            'method': request.method,
            'path': request.path,
            'event': event_detail,
            'user_agent': request.user_agent.string,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # 插入日志记录
        cursor.execute("""
            INSERT INTO user_logs
            (username, access_time, ip_address, action_type, action_detail, module_name)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            username,
            datetime.now(),
            ip_address,
            action_type,
            str(action_detail),
            module_name
        ))

        conn.commit()
    except Exception as e:
        print(f"Error logging system event: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def check_user_logged_in():
    if 'username' not in session:
        flash('Please log in to view this page.')
        return redirect(url_for('login'))
    return None

@app.route('/get_categories_by_version', methods=['GET'])
def get_categories_by_version():
    project_id = request.args.get('project_id')
    version_id = request.args.get('version_id')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT category_id, category_name, parent_category_id, indicator_base_name, unit_indicator
        FROM cost_categories
        WHERE project_id = %s AND version_id = %s
    """, (project_id, version_id))
    all_categories = cursor.fetchall()

    def build_tree(categories, parent_id=None):
        tree = []
        for category in categories:
            if category['parent_category_id'] == parent_id:
                children = build_tree(categories, category['category_id'])
                if children:
                    category['children'] = children
                tree.append(category)
        return tree

    categories_tree = build_tree(all_categories)
    cursor.close()
    conn.close()

    return jsonify({'categories': categories_tree})

@app.route('/success_message')
def success_message():
    return '<h1>数据已保存！</h1>'

@app.route('/logout')
def logout():
    try:
        # 在清除session之前记录退出日
        if 'username' in session:
            username = session['username']
            conn = get_db_connection()
            cursor = conn.cursor()

            # 获取客户端IP
            if request.headers.getlist("X-Forwarded-For"):
                ip_address = request.headers.getlist("X-Forwarded-For")[0]
            else:
                ip_address = request.remote_addr

            # 构建action_detail
            action_detail = {
                'method': request.method,
                'path': request.path,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # 插入退出日志
            cursor.execute("""
                INSERT INTO user_logs
                (username, access_time, ip_address, action_type, action_detail, module_name)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                username,
                datetime.now(),
                ip_address,
                '退出系统',
                str(action_detail),
                '用户管理'
            ))

            conn.commit()
            cursor.close()
            conn.close()

            # 清除session
            session.clear()

    except Exception as e:
        print(f"Error logging logout action: {str(e)}")
        # 确保即使日志记录失败，也要除session
        session.clear()

    return redirect(url_for('login'))

@app.route('/change_password', methods=['GET', 'POST'])
@log_user_action('修改密码', '用户管理')
def change_password():
    if request.method == 'POST':
        username = request.form['username']
        old_password = request.form['old_password']
        new_password = request.form['new_password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user_record = cursor.fetchone()

        if user_record and check_password_hash(user_record['password'], old_password):
            new_password_hash = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password = %s WHERE username = %s", (new_password_hash, username))
            conn.commit()
            flash('Password updated successfully!')
            return redirect(url_for('login'))
        else:
            flash('Incorrect username or old password!')

        cursor.close()
        conn.close()

    return render_template('change_password.html')

@app.route('/query_data')
@log_user_action('查询数据', '数据查询')
def query_data():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT project_id, project_name FROM projects')
    projects = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('query_data.html', projects=projects)

@app.route('/query_item_price', methods=['GET'])
@log_user_action('查询分部分项价格', '数据查询')
def query_item_price():
    try:
        item_name = request.args.get('item_name', '*')
        item_property = request.args.get('item_property', '*')
        unit = request.args.get('unit', '*')
        unit_price = request.args.get('unit_price', '*')
        name_prj = request.args.get('name_prj', '*')
        price_type = request.args.get('price_type', '*')

        conn = get_db_connection()
        if conn is None:
            return jsonify(success=False, error="数据库连接失败"), 500

        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT item_name, item_property, unit, unit_price, name_prj, price_type
            FROM mydata
            WHERE (%s = '*' OR item_name LIKE %s)
              AND (%s = '*' OR item_property LIKE %s)
              AND (%s = '*' OR unit LIKE %s)
              AND (%s = '*' OR unit_price LIKE %s)
              AND (%s = '*' OR name_prj LIKE %s)
              AND (%s = '*' OR price_type LIKE %s)
        """

        params = (
            item_name, f"%{item_name}%" if item_name != '*' else '%',
            item_property, f"%{item_property}%" if item_property != '*' else '%',
            unit, f"%{unit}%" if unit != '*' else '%',
            unit_price, f"%{unit_price}%" if unit_price != '*' else '%',
            name_prj, f"%{name_prj}%" if name_prj != '*' else '%',
            price_type, f"%{price_type}%" if price_type != '*' else '%'
        )

        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify(results)

    except Exception as e:
        print(f"Error in query_item_price: {str(e)}")
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        return jsonify(success=False, error=str(e)), 500

@app.route('/query_all_projects', methods=['GET'])
@log_user_action('查询项目信息', '项目管理')
def query_all_projects():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT p.*, v.version_name,
               p.project_land_area, p.project_count_area, p.prj_type
        FROM projects p
        LEFT JOIN versions v ON p.version_id = v.version_id
    """)
    projects = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify({'projects': projects})

@app.route('/query_single_project_cost', methods=['POST'])
@log_user_action('查询目标成本', '成本管理')
def query_single_project_cost():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    selected_project_id = request.form.get('project_id')
    selected_version_id = request.form.get('version_id')

    # 获取项目建面积
    cursor.execute("SELECT project_CFA FROM projects WHERE project_id = %s", (selected_project_id,))
    project_cfa = cursor.fetchone()['project_CFA']

    cursor.execute("""
        SELECT category_id, category_name, parent_category_id,
               unit_indicator, indicator_base_name,
               construction_area, amount
        FROM cost_categories
        WHERE project_id = %s AND version_id = %s
    """, (selected_project_id, selected_version_id))

    all_categories = cursor.fetchall()

    # 获取开发成本行的总金额
    dev_cost_total = next((category['amount'] for category in all_categories if category['category_name'] == '开发成本'), 0)

    def build_tree(categories, parent_id=None):
        tree = []
        for category in categories:
            if category['parent_category_id'] == parent_id:
                children = build_tree(categories, category['category_id'])
                if children:
                    category['children'] = children
                tree.append(category)
        return tree

    categories_tree = build_tree(all_categories)
    cursor.close()
    conn.close()

    return jsonify({'categories_tree': categories_tree, 'project_cfa': project_cfa, 'dev_cost_total': dev_cost_total})

@app.route('/export_to_excel', methods=['POST'])
@log_user_action('导出Excel', '数据导出')
def export_to_excel():
    if 'username' not in session:
        return redirect(url_for('login'))

    if 'data' not in request.json or 'current_view' not in request.json:
        return jsonify(success=False, error="Missing required parameters"), 400

    export_data = request.json['data']
    current_view = request.json['current_view']  # 从 request.json 中获取，而不是 request.form

    # 创建一个内存中的Excel文件
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()

    # 设置标题格式
    title_format = workbook.add_format({
        'bold': True,
        'align': 'center',
        'valign': 'vcenter',
        'bg_color': '#F4F4F4'
    })

    # 设置数据格式
    data_format = workbook.add_format({
        'align': 'left',
        'valign': 'vcenter'
    })

    # 设置数字格式（带两位小数）
    number_format = workbook.add_format({
        'align': 'right',
        'valign': 'vcenter',
        'num_format': '#,##0.00'
    })

    # 设置百分比格式
    percent_format = workbook.add_format({
        'align': 'right',
        'valign': 'vcenter',
        'num_format': '0.00%'
    })

    if current_view == 'single_project':
        # 导出目标成本数据
        categories_tree = export_data['categories_tree']
        project_cfa = float(export_data.get('project_cfa', 0) or 0)
        dev_cost_total = float(export_data.get('dev_cost_total', 0) or 0)

        titles = ['科目名称', '单位成本', '计算基础', '数量', '总金额', '总建筑面积单方', '费用占比']
        worksheet.write_row('A1', titles, title_format)
        row = 1

        def write_tree_to_excel(tree, row, parent_code='', level=0, is_root=True):
            for index, category in enumerate(tree, 1):
                # 生成科目编码和名称组合，添加缩进
                indented_space = "    " * level  # 使用4个空格作为缩进单位

                # 如果是根节点（开发成本），不显示编号
                if is_root:
                    category_display = f"{indented_space}{category['category_name']}"
                else:
                    # 修改科目编码格式，确保每个层级都有小数点
                    if parent_code:
                        current_code = f"{parent_code}{index}."  # 父级编码已经包含小数点
                    else:
                        current_code = f"{index}."  # 一级科目编码
                    category_display = f"{indented_space}{current_code} {category['category_name']}"

                # 确保数值型转换
                try:
                    amount = float(category.get('amount', 0) or 0)
                    construction_area = float(category.get('construction_area', 0) or 0)
                    unit_indicator = category.get('unit_indicator')
                    # 处理unit_indicator的None值和转换
                    if unit_indicator is None or unit_indicator == '':
                        unit_indicator = '-'
                    elif unit_indicator != '-':
                        try:
                            unit_indicator = float(unit_indicator)
                        except (ValueError, TypeError):
                            unit_indicator = '-'

                    unit_cost = amount / project_cfa if project_cfa and amount else 0
                    cost_ratio = amount / dev_cost_total if dev_cost_total and amount else 0
                except (ValueError, TypeError):
                    amount = 0
                    construction_area = 0
                    unit_cost = 0
                    cost_ratio = 0

                # 写入数据，使用不同的格式
                worksheet.write(row, 0, category_display, data_format)  # 科目编码+名称（带缩进）
                if isinstance(unit_indicator, (int, float)):
                    worksheet.write(row, 1, unit_indicator, number_format)
                else:
                    worksheet.write(row, 1, unit_indicator, data_format)
                worksheet.write(row, 2, category.get('indicator_base_name', '-'), data_format)
                worksheet.write(row, 3, construction_area, number_format)
                worksheet.write(row, 4, amount, number_format)
                worksheet.write(row, 5, unit_cost, number_format)
                worksheet.write(row, 6, cost_ratio, percent_format)

                row += 1
                if 'children' in category:
                    # 对于子节点，传递当前编码作为父级编码
                    row = write_tree_to_excel(category['children'], row,
                                           current_code if not is_root else '',
                                           level + 1, False)
            return row

        write_tree_to_excel(categories_tree, row)

    elif current_view == 'all_projects':
        # 导出项目信息数据
        projects_data = export_data['projects_data']
        titles = ['项目ID', '项目名称', '日期', '城市', '地址', '开发商', '建筑面积', '用地面积',
                 '计容面积', '绿地面积', '室外面积', '项目类型', '版本']
        worksheet.write_row('A1', titles, title_format)
        row = 1

        for project in projects_data:
            worksheet.write_row(row, 0, [
                project['project_id'],
                project['project_name'],
                project['project_date'],
                project['project_city'],
                project['project_address'],
                project['project_developer'],
                project['project_CFA'],
                project.get('project_land_area', '-'),
                project.get('project_count_area', '-'),
                project.get('project_green_area', '-'),
                project.get('project_outdoor_area', '-'),
                project.get('prj_type', '-'),
                project.get('version_name', '-')
            ], data_format)
            row += 1

    elif current_view == 'item_price':
        # 导出分部分项价格数据
        items_data = export_data['items_data']
        titles = ['项目名称', '项特征', '单位', '综合单价', '工程项目名称', '计价类型']
        worksheet.write_row('A1', titles, title_format)
        row = 1

        for item in items_data:
            worksheet.write_row(row, 0, [
                item.get('item_name', '-'),
                item.get('item_property', '-'),
                item.get('unit', '-'),
                item.get('unit_price', '-'),
                item.get('name_prj', '-'),
                item.get('price_type', '-')
            ], data_format)
            row += 1

    workbook.close()
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'exported_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    )

@app.route('/query_buildings_by_project', methods=['POST'])
def query_buildings_by_project():
    project_id = request.form.get('project_id')
    if not project_id:
        return jsonify({'error': 'Missing project ID'}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT building_name, public_facility, building_area, decorated_area, floors, floor_height, decoration_status, building_type, building_structure
        FROM buildings WHERE project_id = %s
    """, (project_id,))
    buildings = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify({'buildings': buildings})

@app.route('/query_buildings_by_project_v2', methods=['POST'])
def query_buildings_by_project_v2():
    project_id = request.form.get('project_id')
    if not project_id:
        return jsonify({'error': 'Missing project ID'}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT building_name, public_facility, building_area, decorated_area, floors, floor_height, decoration_status, building_type, building_structure
        FROM buildings WHERE project_id = %s
    """, (project_id,))
    buildings = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify({'buildings': buildings})

@app.route('/get_version_names', methods=['GET'])
def get_version_names():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT version_name FROM cost_categories")
    versions = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return jsonify({'versions': versions})

@app.route('/get_project_version/<int:project_id>')
@log_user_action('查询项目版本', '版本管理')
def get_project_version(project_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 获取项目相关的所有版本
        cursor.execute("""
            SELECT DISTINCT v.version_id, v.version_name
            FROM versions v
            JOIN projects p ON p.version_id = v.version_id
            WHERE p.project_id = %s
            UNION
            SELECT DISTINCT v.version_id, v.version_name
            FROM versions v
            JOIN buildings b ON b.version_id = v.version_id
            WHERE b.project_id = %s
        """, (project_id, project_id))

        versions = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'versions': versions})
    except Exception as e:
        print(f"Error getting project versions: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/get_project_details/<project_id>', methods=['GET'])
@log_user_action('查询项目详情', '项目管理')
def get_project_details(project_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM projects WHERE project_id = %s", (project_id,))
    project = cursor.fetchone()
    cursor.close()
    conn.close()

    return jsonify(project)

@app.route('/run_compute_cost_categories', methods=['POST'])
def run_compute_cost_categories():
    if 'username' not in session:
        return redirect(url_for('login'))

    data = request.json
    project_id = data.get('project_id')
    version_id = data.get('version_id')
    print("Received run_compute_cost_categories data:", data)  # 调试信息

    if not project_id:
        return jsonify({"error": "Missing project_id parameter"}), 400
    if not version_id:
        return jsonify({"error": "Missing version_id parameter"}), 400  # 检查 version_id

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.callproc('compute_cost_categories', [project_id, version_id])
        conn.commit()
        return jsonify(success=True)
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify(success=False, error=str(err))
    finally:
        cursor.close()
        conn.close()

@app.route('/submit_unit_indicator/<int:project_id>', methods=['POST'])
@log_user_action('提交成本指标', '成本管理')
def submit_unit_indicator(project_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    data = request.json
    version_id = data.pop('version_id', '')  # 添加默认值
    # print("Received submit_unit_indicator data:", data)  # 调试信息

    if not version_id:
        return jsonify(success=False, error="Missing version_id parameter"), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        for category_id, details in data.items():
            if not category_id.isdigit():
                continue
            unit_indicator = details.get('unit_indicator', None)
            category_name = details.get('category_name', None)
            if unit_indicator == '':
                unit_indicator = None

            cursor.execute("""
                INSERT INTO cost_categories (category_id, project_id, version_id, unit_indicator, category_name)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE unit_indicator = VALUES(unit_indicator), category_name = VALUES(category_name)
            """, (category_id, project_id, version_id, unit_indicator, category_name))

        conn.commit()

        # 调用存储过程
        cursor.callproc('compute_cost_categories', [project_id])
        conn.commit()

        return jsonify({'redirect': url_for('success_message')}), 200
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify(success=False, error=str(err))
    finally:
        cursor.close()
        conn.close()

@app.route('/contract_doc', methods=['GET', 'POST'])
@log_user_action('生成合同文档', '文档管理')
def contract_doc():
    if request.method == 'GET':
        return render_template('index2.html')
    elif request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                app.logger.error('未收到数据')
                return jsonify({'success': False, 'message': '未收到数据'}), 400

            # 定义字段中文名映射
            field_names = {
                'project_name': '项目名称',
                'project_type': '项目业态',
                'project_scale': '项目建设规模',
                'project_investment': '项目总投资',
                'project_location': '项目地点',
                'project_nature': '工程性质',
                'construction_unit': '施工单位',
                'supervision_unit': '监理单位',
                'design_unit': '设计单位',
                'contract_name': '合���名称',
                'contract_number': '合同编号',
                'party_a': '甲方',
                'party_b': '乙方',
                'start_date': '开工日期',
                'end_date': '竣工日期',
                'total_days': '工期',
                'contract_model': '承发包模式',
                'pricing_form': '合同计价形式',
                'quality_requirement': '质量要求',
                'project_size': '工程规模',
                'contract_amount': '签约合同金额',
                'advance_payment': '预付款',
                'progress_payment': '进度款',
                'advance_deduction': '预付款扣回',
                'warranty_amount': '质保金额',
                'completion_payment': '竣工款',
                'quality_warranty': '质保金',
                'earth_excavation': '土方开挖',
                'concrete_engineering': '混凝土工程',
                'steel_engineering': '钢筋工程',
                'formwork_engineering': '模板工程',
                'masonry_engineering': '砌筑工程',
                'waterproof_engineering': '防水工程',
                'external_wall_waterproof': '外墙防水',
                'total_measures': '总价措施费',
                'template_engineering': '模板工程',
                'scaffolding_engineering': '脚手架工程',
                'seasonal_measures': '季节性施工措施',
                'vertical_transport': '垂直运输措施',
                'dewatering_measures': '施工降水措施',
                'special_measures': '特殊施工措施',
                'outdoor_facilities': '室外配套设施',
                'redline_outside': '红线外工程',
                'safety_civilization_fee': '安全文明施工费'
            }

            # 创建一个新的 Word 文档
            doc = Document()

            # 设置文档标题
            title = doc.add_heading('工程合同交底文档', level=0)
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER

            # 添加生成时间
            doc.add_paragraph(f'生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

            # 一、项目及合同概述
            doc.add_heading('一、项目及合同概述', level=1)

            # 1. 项目概况
            doc.add_heading('1. 项目概况', level=2)
            project_fields = [
                'project_name', 'project_type', 'project_scale', 'project_investment',
                'project_location', 'project_nature', 'construction_unit',
                'supervision_unit', 'design_unit'
            ]

            for field in project_fields:
                if field in data and data[field]:
                    doc.add_paragraph(f'{field_names.get(field, field)}：{data[field]}')

            # 2. 合同概况
            doc.add_heading('2. 合同概况', level=2)

            # 理合同字段（包含期相关字段）
            contract_fields = [
                'contract_name', 'contract_number', 'party_a', 'party_b',
                'contract_model', 'pricing_form', 'quality_requirement', 'project_size'
            ]

            # 添加工期信息（合并格式）
            if data.get('start_date') and data.get('end_date') and data.get('total_days'):
                doc.add_paragraph(f'工期：{data["start_date"]} 至 {data["end_date"]}，共 {data["total_days"]} 日历天')

            # 添加其他合同字段
            for field in contract_fields:
                if field in data and data[field]:
                    doc.add_paragraph(f'{field_names[field]}：{data[field]}')

            # 3. 合同承包范围
            doc.add_heading('3. 合同承包范围', level=2)

            # 添加单项工程信息
            if data.get('contract_scope'):
                doc.add_paragraph('单项工程及相关分部工程：')

                for building in data['contract_scope']:
                    # 添加单项工程名称（加粗显示）
                    p = doc.add_paragraph()
                    run = p.add_run(building['building'])
                    run.bold = True

                    # 添加该单项工程下的分部工程
                    if building.get('items'):
                        p = doc.add_paragraph()
                        for item in building['items']:
                            # 使用特殊字符"☑"作为选中的复选框
                            checkbox_run = p.add_run('☑ ' + item['name'] + '    ')
                            checkbox_run.font.name = 'Segoe UI Symbol'
                            checkbox_run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
                            checkbox_run.font.size = Pt(10.5)

            # 添加室外配套信息
            if data.get('outdoor_facilities'):
                p = doc.add_paragraph()
                p.add_run('室外配套：').bold = True
                doc.add_paragraph(data['outdoor_facilities'])

            # 添加红线外工程信息
            if data.get('redline_outside'):
                p = doc.add_paragraph()
                p.add_run('红线外：').bold = True
                doc.add_paragraph(data['redline_outside'])

            # 4. 合同金额及构成
            doc.add_heading('4. 合同金额及构成', level=2)
            if data.get('contract_amount'):
                doc.add_paragraph(f"签约合同金额：{data['contract_amount']}")

            # 添加专业分项金额
            if data.get('professional_amounts'):
                doc.add_heading('按专业分项金额情况：', level=3)
                for item in data['professional_amounts']:
                    if item.get('name') and item.get('value'):
                        doc.add_paragraph(f"{item['name']}：{item['value']}")

            # 添加单项工程分项金额
            if data.get('project_amounts'):
                doc.add_heading('单项工程分项金额情况：', level=3)
                for item in data['project_amounts']:
                    if item.get('name') and item.get('value'):
                        doc.add_paragraph(f"{item['name']}：{item['value']}")

            # 二、工程款支付及结算
            doc.add_heading('二、工程款支付及结算', level=1)

            # 5. 付款条件
            doc.add_heading('1. 付款条件', level=2)
            payment_fields = [
                'advance_payment', 'progress_payment', 'advance_deduction',
                'warranty_amount', 'completion_payment', 'quality_warranty'
            ]
            for field in payment_fields:
                if field in data and data[field]:
                    doc.add_paragraph(f"{field_names.get(field, field)}：{data[field]}")

            # 6. 结算条件
            doc.add_heading('2. 结算条件', level=2)
            for i in range(1, 7):
                field = f'settlement_condition_{i}'
                if field in data and data[field]:
                    doc.add_paragraph(data[field])

            # 三、变更签证管理
            doc.add_heading('三、变更签证管理', level=1)

            # 1. ���更签证程序
            doc.add_heading('1. 变更签证程序', level=2)

            if 'change_procedure' in data:
                procedure_data = data['change_procedure']
                procedure_fields = {
                    'initiating_department': '事前审批-发起部门',
                    'approval_points': '事前审批-审批要点',
                    'instruction_issue': '指令下发',
                    'completion_confirmation': '完工确认',
                    'cost_declaration': '费用申报',
                    'cost_approval': '费用审'
                }

                for field, title in procedure_fields.items():
                    if field in procedure_data and procedure_data[field]:
                        doc.add_paragraph(f"{title}：{procedure_data[field]}")

            # 2. 变更成本控制
            doc.add_heading('2. 变更成本控制', level=2)
            if 'change_cost_control' in data and data['change_cost_control']:
                doc.add_paragraph(data['change_cost_control'])

            # 四、清单和合同中需注意的特殊计价原则
            doc.add_heading('四、清单和合同中需注意的特殊计价原则', level=1)
            doc.add_heading('1. 合同清单中需要注意的特殊计价原则', level=2)

            if 'pricing_principles' in data:
                pricing_data = data['pricing_principles']
                pricing_fields = {
                    'earth_excavation': '土方开挖',
                    'rock_excavation': '石方开挖',
                    'backfill': '回填方',
                    'static_blasting': '石方静力爆破',
                    'pile_rock_penetration': '冲孔灌注桩入岩',
                    'rock_recovery': '石方资源回收',
                    'soil_transport': '土方外运',
                    'rock_transport': '石方外运',
                    'muck_truck': '渣土车要求',
                    'earthwork_confirmation': '土石方结算工程量确认原则',
                    'basement_waterproof': '地下室防水',
                    'external_wall_waterproof': '外墙防水',
                    'glass_curtain_wall': '玻璃幕墙',
                    'floor_leveling': '地面找平',
                    'demolition': '拆除工程',
                    'pile_filling_coefficient': '灌注桩充盈系数',
                    'temp_equipment_disposal': '临电设备拆除时残值回收处置'
                }

                for field, title in pricing_fields.items():
                    if field in pricing_data and pricing_data[field]:
                        doc.add_paragraph(f"{title}：{pricing_data[field]}")

            # 五、材料品牌的约定及选取原则
            doc.add_heading('五、材料品牌的约定及选取原则', level=1)

            # 1. 材料品牌选用原则
            doc.add_heading('1. 材料品牌选用原则', level=2)

            if 'material_principles' in data:
                material_data = data['material_principles']

                # 处理选用范围
                if 'brand_selection' in material_data:
                    brand_data = material_data['brand_selection']
                    p = doc.add_paragraph()
                    p.add_run('选用范围：')

                    brand_options = {
                        'company_brand': '公司品牌库',
                        'district_brand': '区工务署品牌库',
                        'city_brand': '市工务署品牌库',
                        'top30_brand': '地产30强品牌库',
                        'other_brand': '其他'
                    }

                    selected_brands = []
                    for key, label in brand_options.items():
                        if key in brand_data and brand_data[key]:
                            selected_brands.append(label)

                    if selected_brands:
                        p.add_run('\n ' + '\n '.join(selected_brands))

                    # 添加档次信息
                    if 'brand_level' in brand_data and brand_data['brand_level']:
                        p = doc.add_paragraph()
                        p.add_run('档次：')
                        p.add_run(f"\n{brand_data['brand_level']}")

                # 2. 材料品牌确认程序
                doc.add_heading('2. 材料品牌确认程序', level=2)

                # 处理库内品牌确认程序
                if 'in_library_confirmation' in material_data and material_data['in_library_confirmation']:
                    p = doc.add_paragraph()
                    p.add_run('库内品牌确认程序：')
                    p.add_run(f"\n{material_data['in_library_confirmation']}")

                # 处理库外品牌确认流程
                if 'out_library_confirmation' in material_data and material_data['out_library_confirmation']:
                    p = doc.add_paragraph()
                    p.add_run('库外品牌确认流程：')
                    p.add_run(f"\n{material_data['out_library_confirmation']}")

            # 六、发包人工作中需要注意的事项
            doc.add_heading('六、发包人工作中需要注意的事项', level=1)

            employer_fields = [
                ('employer_notes', '注意事项'),
                ('work_requirements', '工作要求'),
                ('special_requirements', '特殊要求')
            ]

            for field, title in employer_fields:
                if field in data and data[field]:
                    doc.add_paragraph(f"{title}：{data[field]}")  # 修改：直接添加内容，不需要二级标题

            # 七、措施费的有关特殊情况说明
            doc.add_heading('七、措施费的有关特殊情况说明', level=1)

            if data.get('measure_notes'):
                doc.add_paragraph(data['measure_notes'])

            measure_fields = [
                ('total_measures', '1. 总措施费'),
                ('template_engineering', '2. 模板工程'),
                ('scaffolding_engineering', '3. 脚手架工程'),
                ('seasonal_measures', '4. 季节性施工措施费'),
                ('vertical_transport', '5. 垂直运输费'),
                ('dewatering_measures', '6. 排水措施费'),
                ('special_measures', '7. 特殊措施费')
            ]

            for field, title in measure_fields:
                if field in data and data[field]:
                    doc.add_paragraph(f"{title}：")
                    doc.add_paragraph(data[field])

            # 保存文档到内存中
            doc_stream = BytesIO()
            doc.save(doc_stream)
            doc_stream.seek(0)

            # 生成文件名（使用英文和数字）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f'Contract_Doc_{timestamp}.docx'

            # 返回文件，设置正确的 MIME 类型和文件名
            response = send_file(
                doc_stream,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                as_attachment=True,
                download_name=safe_filename
            )

            # 添加必要的响应头，使用 URL 编码的文件名
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

            # 使用 ASCII 文件名
            response.headers["Content-Disposition"] = f"attachment; filename={safe_filename}"

            return response

        except Exception as e:
            app.logger.error(f"Error generating document: {str(e)}\n{traceback.format_exc()}")
            return jsonify({'success': False, 'message': f'生成文档失败：{str(e)}'}), 500

@app.route('/download_doc/<filename>')
@log_user_action('下载文档', '文档管理')
def download_doc(filename):
    try:
        doc_dir = os.path.join(app.static_folder, 'documents')
        return send_file(
            os.path.join(doc_dir, filename),
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'下载文档失败：{str(e)}'
        }), 500

# 修改日志记录装器
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

# 修改检查用户是否有权限查看日志的函数
def has_log_access(username):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 使用log_viewers表检查用户是否有日志访问权限
        cursor.execute("SELECT can_view_logs FROM log_viewers WHERE username = %s", (username,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        return result and result['can_view_logs'] == 1
    except Exception as e:
        print(f"Error checking log access: {str(e)}")
        return False

# 修改日志查看路
@app.route('/view_logs')
def view_logs():
    if 'username' not in session:
        return redirect(url_for('login'))

    if not has_log_access(session['username']):
        flash('您没有权限访问此页面')
        return redirect(url_for('index'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # 获取筛选参数
            username = request.args.get('username', '')
            start_date = request.args.get('start_date', '')
            end_date = request.args.get('end_date', '')
            action_type = request.args.get('action_type', '')

            # 获取分页参数
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 30, type=int)
            show_all = request.args.get('show_all', '0')

            # 构建基础查询
            base_sql = "FROM user_logs WHERE 1=1"
            params = []

            if username:
                base_sql += " AND username = %s"
                params.append(username)
            if start_date:
                base_sql += " AND DATE(access_time) >= %s"
                params.append(start_date)
            if end_date:
                base_sql += " AND DATE(access_time) <= %s"
                params.append(end_date)
            if action_type:
                base_sql += " AND action_type = %s"
                params.append(action_type)

            # 计算总记录数
            count_sql = f"SELECT COUNT(*) as total {base_sql}"
            cursor.execute(count_sql, params)
            total_records = cursor.fetchone()['total']

            # 获取日志数据
            sql = f"SELECT * {base_sql} ORDER BY access_time DESC"
            if show_all != '1':
                sql += f" LIMIT {per_page} OFFSET {(page - 1) * per_page}"

            cursor.execute(sql, params)
            logs = cursor.fetchall()

            # 获取筛选选项
            cursor.execute("SELECT DISTINCT username FROM user_logs ORDER BY username")
            usernames = [row['username'] for row in cursor.fetchall()]

            cursor.execute("SELECT DISTINCT action_type FROM user_logs ORDER BY action_type")
            action_types = [row['action_type'] for row in cursor.fetchall()]

            # 计算总页数
            total_pages = (total_records + per_page - 1) // per_page if show_all != '1' else 1

            # 计算当前页显示的记录范围
            current_page_start = (page - 1) * per_page + 1
            current_page_end = min(page * per_page, total_records)

            return render_template('view_logs.html',
                                logs=logs,
                                usernames=usernames,
                                action_types=action_types,
                                page=page,
                                per_page=per_page,
                                total_pages=total_pages,
                                total_records=total_records,
                                show_all=show_all,
                                min=min,  # 添加min函数到模板上下文
                                current_page_start=current_page_start,
                                current_page_end=current_page_end)

        except Exception as e:
            print(f"Error in view_logs query: {str(e)}")
            flash('查询日志时发生错误')
            return redirect(url_for('index'))
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        print(f"Error in view_logs: {str(e)}")
        flash('系统错误')
        return redirect(url_for('index'))

# 为查询分部分项价格的相关路由添加装饰器
@app.route('/get_cost_categories/<int:project_id>/<int:version_id>')
@log_user_action('查询分部分项价格', '成本管理')
def get_cost_categories(project_id, version_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT category_id, category_name, parent_category_id,
                   unit_indicator, indicator_base_name, amount
            FROM cost_categories
            WHERE project_id = %s AND version_id = %s
        """, (project_id, version_id))
        categories = cursor.fetchall()
        return jsonify(categories)
    except Exception as e:
        print(f"Error getting cost categories: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/get_cost_category_info/<int:category_id>')
@log_user_action('查询分部分项详情', '成本管理')
def get_cost_category_info(category_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM cost_categories
            WHERE category_id = %s
        """, (category_id,))
        category = cursor.fetchone()
        return jsonify(category)
    except Exception as e:
        print(f"Error getting cost category info: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/get_unit_indicators/<int:project_id>/<int:version_id>')
@log_user_action('查询单位指标', '成本管理')
def get_unit_indicators(project_id, version_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT category_id, category_name, unit_indicator
            FROM cost_categories
            WHERE project_id = %s AND version_id = %s
        """, (project_id, version_id))
        indicators = cursor.fetchall()
        return jsonify(indicators)
    except Exception as e:
        print(f"Error getting unit indicators: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/get_cost_details/<int:project_id>/<int:version_id>')
@log_user_action('查询成本明细', '成本管理')
def get_cost_details(project_id, version_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM cost_categories
            WHERE project_id = %s AND version_id = %s
        """, (project_id, version_id))
        details = cursor.fetchall()
        return jsonify(details)
    except Exception as e:
        print(f"Error getting cost details: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/update_cost_category/<int:category_id>', methods=['POST'])
@log_user_action('更新分部分项', '成本管理')
def update_cost_category(category_id):
    if not request.is_json:
        return jsonify({'error': 'Invalid request format'}), 400

    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE cost_categories
            SET unit_indicator = %s,
                indicator_base_name = %s
            WHERE category_id = %s
        """, (data.get('unit_indicator'), data.get('indicator_base_name'), category_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        print(f"Error updating cost category: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/delete_data')
@log_user_action('访问删除数据页面', '数据管理')
def delete_data():
    if 'username' not in session:
        return redirect(url_for('login'))

    if not has_delete_permission(session['username']):
        flash('您没有删除数据的权限')
        return redirect(url_for('homepage'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 修改 SQL 查询以包含版本信息
    cursor.execute("""
        SELECT p.*, v.version_name,
        (SELECT COUNT(*) FROM buildings b WHERE b.project_id = p.project_id) as building_count
        FROM projects p
        LEFT JOIN versions v ON p.version_id = v.version_id
        ORDER BY p.project_name
    """)
    projects = cursor.fetchall()

    # 获取每个项目的楼宇信息
    for project in projects:
        cursor.execute("""
            SELECT b.*, v.version_name as building_version_name
            FROM buildings b
            LEFT JOIN versions v ON b.version_id = v.version_id
            WHERE b.project_id = %s
        """, (project['project_id'],))
        project['buildings'] = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('delete_data.html', projects=projects)

@app.route('/delete_project/<int:project_id>', methods=['DELETE'])
@log_user_action('删除项目', '数据管理')
def delete_project(project_id):
    if 'username' not in session:
        return jsonify(success=False, message='请先登录')

    if not has_delete_permission(session['username']):
        return jsonify(success=False, message='您没有删除数据的权限')

    # 获取请求中的密码
    data = request.json
    password = data.get('password')

    if not password:
        return jsonify(success=False, message='请输入密码')

    # 验证密码
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT password FROM users WHERE username = %s", (session['username'],))
        user = cursor.fetchone()

        if not user or not check_password_hash(user['password'], password):
            return jsonify(success=False, message='密码错误')

        # 密码验证通过，执行删除操作
        cursor.execute("DELETE FROM projects WHERE project_id = %s", (project_id,))
        conn.commit()
        return jsonify(success=True)
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify(success=False, message=str(err))
    finally:
        cursor.close()
        conn.close()

@app.route('/delete_building/<int:building_id>', methods=['DELETE'])
@log_user_action('删除楼宇', '数据管理')
def delete_building(building_id):
    if 'username' not in session:
        return jsonify(success=False, message='请先登录')

    if not has_delete_permission(session['username']):
        return jsonify(success=False, message='您没有删除数据的权限')

    # 获取请求中的密码
    data = request.json
    password = data.get('password')

    if not password:
        return jsonify(success=False, message='请输入密码')

    # 验证密码
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT password FROM users WHERE username = %s", (session['username'],))
        user = cursor.fetchone()

        if not user or not check_password_hash(user['password'], password):
            return jsonify(success=False, message='密码错误')

        # 获取楼宇信息用于重新计算成本
        cursor.execute("SELECT project_id FROM buildings WHERE building_id = %s", (building_id,))
        building_info = cursor.fetchone()

        if building_info:
            project_id = building_info['project_id']
            # 删除楼宇记录
            cursor.execute("DELETE FROM buildings WHERE building_id = %s", (building_id,))
            # 重新计算成本类别
            cursor.callproc('compute_cost_categories', [project_id])

        conn.commit()
        return jsonify(success=True)
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify(success=False, message=str(err))
    finally:
        cursor.close()
        conn.close()

# 添加权限检查函数
def has_delete_permission(username):
    if not username:
        return False

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT COUNT(*) as has_permission
            FROM users u
            JOIN user_permissions up ON u.user_id = up.user_id
            JOIN permissions p ON up.permission_id = p.permission_id
            WHERE u.username = %s AND p.permission_name = 'delete_data'
        """, (username,))

        result = cursor.fetchone()
        return bool(result['has_permission']) if result else False
    finally:
        cursor.close()
        conn.close()

# 添加到模板全局函数
@app.context_processor
def utility_processor():
    return {
        'has_delete_permission': has_delete_permission
    }

@app.route('/get_all_projects', methods=['GET'])
def get_all_projects():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 获取所有项目的基本信息
        cursor.execute("""
            SELECT p.project_id, p.project_name
            FROM projects p
            ORDER BY p.project_name
        """)

        projects = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'projects': projects})
    except Exception as e:
        print(f"Error getting projects: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/compare_projects', methods=['POST'])
@log_user_action('对比项目数据', '数据对比')
def compare_projects():
    try:
        # 确保数据库连接在整个操作过程中保持活跃
        conn = get_db_connection()
        conn.ping(reconnect=True)  # 添加自动重连
        cursor = conn.cursor(dictionary=True)

        data = request.json
        projects = data.get('projects', [])

        if len(projects) < 2:
            return jsonify({'success': False, 'message': '至少需要选择两个项目进行对比'}), 400

        comparison_data = {
            'projects': [],
            'categories': []
        }

        project_areas = {}

        try:
            # 1. 获取所有项目的类别结构
            project_ids = [str(p['project_id']) for p in projects]
            version_ids = [str(p['version_id']) for p in projects]

            # 修改SQL查询，使用正确的参数占位符
            cursor.execute("""
                WITH RECURSIVE category_hierarchy AS (
                    -- 基础查询
                    SELECT
                        cc.category_id,
                        cc.category_name,
                        cc.parent_category_id
                    FROM cost_categories cc
                    WHERE cc.project_id IN ({}) AND cc.version_id IN ({})

                    UNION

                    -- 递归查询父类别
                    SELECT
                        p.category_id,
                        p.category_name,
                        p.parent_category_id
                    FROM cost_categories p
                    INNER JOIN category_hierarchy ch ON ch.parent_category_id = p.category_id
                )
                SELECT
                    ch.category_id,
                    ch.category_name,
                    ch.parent_category_id
                FROM (
                    SELECT DISTINCT category_id, category_name, parent_category_id
                    FROM category_hierarchy
                ) ch
                ORDER BY ch.category_id
            """.format(','.join(['%s'] * len(project_ids)),
                      ','.join(['%s'] * len(version_ids))),
            project_ids + version_ids)

            all_categories = cursor.fetchall()

            # 2. 初始化类别数据结构
            for category in all_categories:
                comparison_data['categories'].append({
                    'category_id': category['category_id'],
                    'category_name': category['category_name'],
                    'parent_category_id': category['parent_category_id'],
                    'values': {}
                })

            # 3. 获取每个项目的数据
            for project in projects:
                # 获取项目基本信息
                cursor.execute("""
                    SELECT p.project_id, p.project_name, p.project_count_area,
                           v.version_id, v.version_name
                    FROM projects p
                    JOIN versions v ON v.version_id = %s
                    WHERE p.project_id = %s
                """, (project['version_id'], project['project_id']))

                project_info = cursor.fetchone()
                if not project_info:
                    continue

                # 存储项目面积信息
                project_areas[str(project_info['project_id'])] = float(project_info['project_count_area'])  # 添加这行

                comparison_data['projects'].append({
                    'project_id': project_info['project_id'],
                    'project_name': project_info['project_name'],
                    'version_id': project_info['version_id'],
                    'version_name': project_info['version_name'],
                    'project_count_area': float(project_info['project_count_area'])
                })

                # 4. 获取该项目的成本数据
                cursor.execute("""
                    SELECT
                        category_id,
                        category_name,
                        parent_category_id,
                        COALESCE(amount, 0) as amount,
                        COALESCE(unit_indicator, 0) as unit_indicator
                    FROM cost_categories
                    WHERE project_id = %s AND version_id = %s
                    ORDER BY category_id
                """, (project['project_id'], project['version_id']))

                project_costs = cursor.fetchall()

                # 5. 更新类别数据
                for cost in project_costs:
                    category_entry = next(
                        (c for c in comparison_data['categories'] if c['category_id'] == cost['category_id']),
                        None
                    )
                    if category_entry:
                        category_entry['values'][str(project_info['project_id'])] = {
                            'amount': float(cost['amount']),
                            'unit_indicator': float(cost['unit_indicator'])
                        }

            # 构建树形结构和计算父节点数据
            def build_tree_and_calculate(categories):
                # 使用外部的project_areas变量
                nonlocal project_areas

                # 创建节点映射，确保每个category_name只有一个节点，但对于主体建安工程费和公共配套设施费的子节点特殊处理
                nodes_map = {}
                # 存储主体建安工程费节点和公共配套设施费节点的ID，用于稍后判断
                main_construction_id = None
                public_facilities_id = None

                # 先找到主体建安工程费节点和公共配套设施费节点
                for cat in categories:
                    if cat['category_name'] == '主体建安工程费':
                        main_construction_id = cat['category_id']
                    elif cat['category_name'] == '公共配套设施费':
                        public_facilities_id = cat['category_id']

                # 创建父子关系映射，用于后续构建树
                parent_child_map = {}
                for cat in categories:
                    parent_id = cat['parent_category_id']
                    if parent_id not in parent_child_map:
                        parent_child_map[parent_id] = []
                    parent_child_map[parent_id].append(cat)

                # 标记特殊节点的子孙节点
                special_parent_ids = set([main_construction_id, public_facilities_id])
                special_descendants = set()

                # 存储节点之间的父子关系，用于后续查找子孙节点
                child_parent_map = {}
                for cat in categories:
                    child_id = cat['category_id']
                    parent_id = cat['parent_category_id']
                    child_parent_map[child_id] = parent_id

                # 判断一个节点是否是特殊节点的子孙节点
                def is_descendant_of_special_node(node_id):
                    current_id = node_id
                    while current_id is not None:
                        parent_id = child_parent_map.get(current_id)
                        if parent_id in special_parent_ids:
                            return True, parent_id
                        current_id = parent_id
                    return False, None

                # 给所有节点添加特殊标记，以便后续创建节点时使用
                node_special_flags = {}
                for cat in categories:
                    node_id = cat['category_id']
                    is_special, special_parent = is_descendant_of_special_node(node_id)
                    if is_special:
                        node_special_flags[node_id] = special_parent
                        special_descendants.add(node_id)

                # 为每个节点创建一个项目特定的键
                node_project_keys = {}
                for cat in categories:
                    node_id = cat['category_id']
                    # 如果节点是特殊节点的子孙，则为每个项目创建特定的键
                    if node_id in special_descendants or cat['parent_category_id'] in special_parent_ids:
                        project_ids = list(cat['values'].keys()) if 'values' in cat and cat['values'] else []
                        for project_id in project_ids:
                            key = f"{cat['category_name']}_{project_id}_{node_id}"
                            if node_id not in node_project_keys:
                                node_project_keys[node_id] = {}
                            node_project_keys[node_id][project_id] = key

                # 处理所有节点
                for cat in categories:
                    category_id = cat['category_id']
                    parent_id = cat['parent_category_id']

                    # 对于主体建安工程费、公共配套设施费的子孙节点，按项目分别处理
                    if category_id in special_descendants or parent_id in special_parent_ids:
                        project_ids = list(cat['values'].keys()) if 'values' in cat and cat['values'] else []
                        for project_id in project_ids:
                            # 为当前节点生成唯一键
                            if category_id in node_project_keys and project_id in node_project_keys[category_id]:
                                node_key = node_project_keys[category_id][project_id]
                            else:
                                node_key = f"{cat['category_name']}_{project_id}_{category_id}"

                            if node_key not in nodes_map:
                                # 判断节点类型
                                parent_type = None
                                if parent_id == main_construction_id:
                                    parent_type = 'main_construction'
                                elif parent_id == public_facilities_id:
                                    parent_type = 'public_facilities'
                                elif category_id in special_descendants:
                                    special_parent_id = node_special_flags.get(category_id)
                                    parent_type = 'main_construction' if special_parent_id == main_construction_id else 'public_facilities'

                                # 创建节点
                                project_specific_node = {
                                    'id': category_id,
                                    'name': cat['category_name'],
                                    'parent_id': parent_id,
                                    'children': [],
                                    'values': {},
                                    'level': 0,
                                    'project_id': project_id,  # 添加项目ID标记
                                    'parent_type': parent_type,  # 标记父节点类型
                                    'node_key': node_key  # 保存唯一键以便后续查找
                                }

                                # 添加数据值
                                if 'values' in cat and project_id in cat['values']:
                                    project_specific_node['values'][project_id] = cat['values'][project_id]

                                nodes_map[node_key] = project_specific_node

                    # 常规处理其他节点
                    elif str(cat['category_id']) not in nodes_map:
                        # 判断是否是主体建安工程费或公共配套设施费的子孙节点
                        is_special_descendant = False
                        special_parent_type = None

                        if main_construction_id is not None and is_descendant_of_special_node(cat['category_id'])[0]:
                            is_special_descendant, special_parent = is_descendant_of_special_node(cat['category_id'])
                            if special_parent == main_construction_id:
                                special_parent_type = 'main_construction'
                            elif special_parent == public_facilities_id:
                                special_parent_type = 'public_facilities'

                        # 创建节点，使用category_id作为唯一标识
                        # 所有节点默认使用水平显示模式，包括主体建安工程费和公共配套设施费的子节点
                        nodes_map[str(cat['category_id'])] = {
                            'id': category_id,
                            'name': cat['category_name'],
                            'parent_id': parent_id,
                            'children': [],
                            'values': cat['values'].copy() if 'values' in cat else {},
                            'level': 0,
                            'display_mode': 'horizontal',  # 所有节点都使用水平显示模式
                            'parent_type': special_parent_type
                        }
                    else:
                        # 如果节点已存在，合并values
                        existing_values = nodes_map[str(cat['category_id'])]['values']
                        new_values = cat['values'] if 'values' in cat else {}
                        for project_id, value in new_values.items():
                            if project_id in existing_values:
                                existing_values[project_id]['amount'] += value['amount']
                                if project_id in project_areas and project_areas[project_id] > 0:
                                    existing_values[project_id]['unit_indicator'] = existing_values[project_id]['amount'] / project_areas[project_id]
                            else:
                                existing_values[project_id] = value.copy()

                # 构建树形结构
                root_nodes = []
                # 首先添加根节点
                for node_key, node in nodes_map.items():
                    if node['parent_id'] is None or node['name'] == '开发成本':  # 特殊处理"开发成本"
                        root_nodes.append(node)

                # 然后处理子节点
                for node_key, node in nodes_map.items():
                    if node['parent_id'] is not None and node['name'] != '开发成本':
                        # 对于特殊节点的子孙节点
                        if '_' in node_key:
                            if 'project_id' not in node:
                                continue

                            project_id = node['project_id']
                            parent_id = node['parent_id']

                            # 处理主体建安工程费和公共配套设施费的直接子节点
                            if parent_id == main_construction_id:
                                # 使用ID查找主体建安工程费节点
                                main_construction_node = next((n for n in nodes_map.values() if n['id'] == main_construction_id), None)
                                if main_construction_node:
                                    main_construction_node['children'].append(node)
                            elif parent_id == public_facilities_id:
                                # 使用ID查找公共配套设施费节点
                                public_facilities_node = next((n for n in nodes_map.values() if n['id'] == public_facilities_id), None)
                                if public_facilities_node:
                                    public_facilities_node['children'].append(node)
                            # 处理更深层次的子节点
                            else:
                                # 查找父节点
                                parent_found = False
                                # 如果父节点ID在特殊节点项目键映射中
                                if parent_id in node_project_keys and project_id in node_project_keys[parent_id]:
                                    parent_key = node_project_keys[parent_id][project_id]
                                    if parent_key in nodes_map:
                                        parent_node = nodes_map[parent_key]
                                        parent_node['children'].append(node)
                                        parent_found = True

                                # 如果未找到父节点，尝试遍历所有节点查找
                                if not parent_found:
                                    for potential_key, potential_node in nodes_map.items():
                                        if '_' in potential_key and potential_node['id'] == parent_id and potential_node.get('project_id') == project_id:
                                            potential_node['children'].append(node)
                                            parent_found = True
                                            break
                        # 常规处理其他节点
                        else:
                            # 使用ID查找父节点
                            parent = next((n for n in nodes_map.values() if n['id'] == node['parent_id']), None)
                            if parent:
                                # 添加特殊节点标记
                                if parent['id'] == main_construction_id or parent['id'] == public_facilities_id:
                                    # 保持水平显示模式，但添加父节点类型标记
                                    node['parent_type'] = 'main_construction' if parent['id'] == main_construction_id else 'public_facilities'
                                parent['children'].append(node)

                # 返回根节点列表
                return root_nodes

            tree_data = build_tree_and_calculate(comparison_data['categories'])
            comparison_data['categories'] = tree_data

            # 在返回结果之前确保提交事务
            conn.commit()

            return jsonify({
                'success': True,
                'comparison_data': comparison_data
            })

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        print(f"Error in compare_projects: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    print("Starting application setup...")
    setup_logging()
    print("Logging setup completed, starting Flask app...")
    try:
        app.run(host='0.0.0.0', port=5001)
    except Exception as e:
        print(f"Error starting application: {str(e)}")
        print(f"Error traceback: {traceback.format_exc()}")
        sys.stdout.flush()