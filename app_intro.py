'''
成本服务器应用程序 (Cost Server)

这是一个基于Flask的Web应用程序，用于管理和计算项目成本。
主要功能包括：
- 用户认证和授权管理
- 项目数据管理
- 楼宇和构筑物信息管理
- 成本计算与分析
- 报表生成
- 用户操作日志记录

技术栈：
- 后端：Python + Flask
- 数据库：MySQL
- 前端：HTML + CSS + JavaScript
- 文档处理：docx, xlsxwriter

使用说明：
1. 安装依赖：pip install -r requirements.txt
2. 配置数据库：编辑config.py文件
3. 运行应用：python app.py
'''

# 应用结构说明

'''
app.py - 主应用程序
config.py - 数据库配置文件
requirements.txt - 依赖包列表

templates/ - HTML模板文件
  ├── login.html - 登录页面
  ├── homepage.html - 主页面
  ├── add_project.html - 添加项目页面
  ├── add_building.html - 添加楼宇页面
  ├── enter_data.html - 数据录入页面
  ├── query_data.html - 数据查询页面
  ├── delete_data.html - 数据删除页面
  └── ...

static/ - 静态资源文件
  ├── css/ - CSS样式文件
  ├── js/ - JavaScript文件
  └── documents/ - 文档存储目录

src/ - 源代码
  ├── components/ - 组件文件
  └── styles/ - 样式文件
'''

# 路由说明

'''
/ - 首页
/login - 登录页面
/logout - 退出登录
/enter_data - 数据录入页面
/add_project - 添加项目
/add_building - 添加楼宇
/query_data - 数据查询
/delete_data - 数据删除
/change_password - 修改密码
/view_logs - 查看日志
'''