/**
 * 项目管理系统主要JavaScript文件
 */

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    console.log('页面已加载完成');
    
    // 项目选择变更时获取对应的版本
    const projectSelect = document.getElementById('project_id');
    if (projectSelect) {
        projectSelect.addEventListener('change', function() {
            const projectId = this.value;
            if (projectId) {
                fetchVersions(projectId);
            } else {
                // 如果没有选择项目，清空版本下拉列表
                const versionSelect = document.getElementById('version_id');
                versionSelect.innerHTML = '<option value="">请选择</option>';
            }
        });
    }
    
    // 表单验证
    const forms = document.querySelectorAll('.needs-validation');
    if (forms.length > 0) {
        Array.from(forms).forEach(form => {
            form.addEventListener('submit', function(event) {
                if (!form.checkValidity()) {
                    event.preventDefault();
                    event.stopPropagation();
                }
                form.classList.add('was-validated');
            }, false);
        });
    }
    
    // 初始化数据表格
    initializeTables();
    
    // 初始化日期选择器
    initializeDatepickers();
});

/**
 * 获取项目对应的版本列表
 * @param {string} projectId - 项目ID
 */
function fetchVersions(projectId) {
    fetch(`/get_versions/${projectId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('网络响应异常');
            }
            return response.json();
        })
        .then(data => {
            const versionSelect = document.getElementById('version_id');
            versionSelect.innerHTML = '<option value="">请选择</option>';
            
            data.versions.forEach(version => {
                const option = document.createElement('option');
                option.value = version.version_id;
                option.textContent = version.version_name;
                versionSelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('获取版本失败:', error);
            alert('获取版本失败，请稍后重试');
        });
}

/**
 * 初始化数据表格
 */
function initializeTables() {
    const tables = document.querySelectorAll('.data-table');
    if (tables.length > 0) {
        tables.forEach(table => {
            // 添加表格排序和搜索功能
            const searchInput = document.createElement('input');
            searchInput.type = 'text';
            searchInput.placeholder = '搜索...';
            searchInput.className = 'form-control mb-3';
            
            table.parentNode.insertBefore(searchInput, table);
            
            searchInput.addEventListener('keyup', function() {
                const searchText = this.value.toLowerCase();
                const rows = table.querySelectorAll('tbody tr');
                
                rows.forEach(row => {
                    const text = row.textContent.toLowerCase();
                    row.style.display = text.includes(searchText) ? '' : 'none';
                });
            });
        });
    }
}

/**
 * 初始化日期选择器
 */
function initializeDatepickers() {
    const datepickers = document.querySelectorAll('.datepicker');
    if (datepickers.length > 0) {
        datepickers.forEach(input => {
            // 日期选择器的初始化代码，具体实现根据使用的库而定
            console.log('初始化日期选择器:', input.id);
        });
    }
}

/**
 * 显示确认对话框
 * @param {string} message - 确认消息
 * @param {Function} callback - 确认后的回调函数
 */
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

/**
 * 删除项目
 * @param {string} projectId - 项目ID
 */
function deleteProject(projectId) {
    confirmAction('确定要删除该项目吗？此操作不可恢复！', function() {
        fetch(`/delete_project/${projectId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('删除失败');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                alert('项目删除成功');
                // 刷新页面
                window.location.reload();
            } else {
                alert('删除失败: ' + data.message);
            }
        })
        .catch(error => {
            console.error('删除项目时出错:', error);
            alert('删除项目时出错，请稍后重试');
        });
    });
}