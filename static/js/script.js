function generateDocument() {
    const submitButton = document.getElementById('generate-doc');
    submitButton.disabled = true;
    submitButton.textContent = '正在生成文档...';

    // 显示加载提示
    const loadingMessage = document.createElement('div');
    loadingMessage.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(0, 0, 0, 0.8);
        color: white;
        padding: 20px;
        border-radius: 8px;
        z-index: 9999;
    `;
    loadingMessage.textContent = '正在生成文档，请稍候...';
    document.body.appendChild(loadingMessage);

    // 定义清理函数
    const cleanup = () => {
        if (document.body.contains(loadingMessage)) {
            document.body.removeChild(loadingMessage);
        }
        submitButton.disabled = false;
        submitButton.textContent = '生成合同交底文档';
    };

    try {
        // 收集表单数据
        const formData = {
            // 项目概况
            project_name: document.querySelector('input[name="project_name"]')?.value || '',
            project_type: document.querySelector('select[name="project_type"]')?.value || '',
            project_scale: document.querySelector('input[name="project_scale"]')?.value || '',
            project_investment: document.querySelector('input[name="project_investment"]')?.value || '',
            project_location: document.querySelector('input[name="project_location"]')?.value || '',
            project_nature: document.querySelector('input[name="project_nature"]')?.value || '',
            construction_unit: document.querySelector('input[name="construction_unit"]')?.value || '',
            supervision_unit: document.querySelector('input[name="supervision_unit"]')?.value || '',
            design_unit: document.querySelector('input[name="design_unit"]')?.value || '',

            // 合同概况
            contract_name: document.querySelector('input[name="contract_name"]')?.value || '',
            contract_number: document.querySelector('input[name="contract_number"]')?.value || '',
            party_a: document.querySelector('input[name="party_a"]')?.value || '',
            party_b: document.querySelector('input[name="party_b"]')?.value || '',
            start_date: document.querySelector('input[name="start_date"]')?.value || '',
            end_date: document.querySelector('input[name="end_date"]')?.value || '',
            total_days: document.querySelector('input[name="total_days"]')?.value || '',
            contract_model: document.querySelector('select[name="contract_model"]')?.value || '',
            pricing_form: document.querySelector('select[name="pricing_form"]')?.value || '',
            project_size: document.querySelector('input[name="project_size"]')?.value || '',

            // 合同承包范围
            contract_scope: (() => {
                const buildings = [];
                const buildingDivs = document.querySelectorAll('#building-list > div');
                
                buildingDivs.forEach(div => {
                    const buildingName = div.querySelector('h4')?.textContent || '';
                    const checkedBoxes = div.querySelectorAll('input[type="checkbox"]:checked');
                    
                    if (buildingName) {
                        buildings.push({
                            building: buildingName,
                            items: Array.from(checkedBoxes).map(checkbox => ({
                                name: checkbox.parentElement.textContent.trim()
                            }))
                        });
                    }
                });
                return buildings;
            })(),

            outdoor_facilities: document.querySelector('input[name="outdoor_facilities"]')?.value || '',
            redline_outside: document.querySelector('input[name="outside_redline"]')?.value || '',

            // 合同金额及构成
            contract_amount: document.querySelector('input[name="contract_amount"]')?.value || '',
            professional_amounts: Array.from(document.querySelectorAll('#added-amounts .amount-item')).map(item => ({
                name: item.querySelector('input[name="amount_name"]')?.value || '',
                value: item.querySelector('input[name="amount_value"]')?.value || ''
            }))
        };

        // 发送数据到服务器
        fetch('/contract_doc', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.message || '服务器响应错误');
                });
            }
            return response.blob();
        })
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `工程合同交底文档_${new Date().toISOString().slice(0,10)}.docx`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
            alert('文档生成成功！');
        })
        .catch(error => {
            console.error('Error:', error);
            alert('生成文档失败：' + error.message);
        })
        .finally(cleanup);
    } catch (error) {
        console.error('Error:', error);
        alert('生成文档失败：' + error.message);
        cleanup();
    }
}

// 项目数据编辑功能
function enableEdit(id) {
    const row = document.getElementById(`project-${id}`);
    if (!row) return;
    
    const cells = row.querySelectorAll('td');
    cells.forEach((cell, index) => {
        // 跳过操作按钮列
        if (index === cells.length - 1) return;
        
        const content = cell.innerText.trim();
        const fieldName = cell.getAttribute('data-field');
        
        if (fieldName) {
            // 日期字段特殊处理
            if (fieldName === 'start_date') {
                cell.innerHTML = `<input type="date" class="form-control" name="${fieldName}" value="${content}">`;
            } 
            // 下拉选择特殊处理
            else if (fieldName === 'project_type') {
                const types = ['住宅', '商业', '办公', '混合', '其他'];
                let options = types.map(type => 
                    `<option value="${type}" ${content === type ? 'selected' : ''}>${type}</option>`
                ).join('');
                
                cell.innerHTML = `<select class="form-control" name="${fieldName}">${options}</select>`;
            }
            // 数字类型特殊处理
            else if (['building_area', 'underground_area', 'commercial_area', 'villa_area', 'total_investment'].includes(fieldName)) {
                cell.innerHTML = `<input type="number" step="0.01" class="form-control" name="${fieldName}" value="${content}">`;
            }
            // 普通文本字段
            else {
                cell.innerHTML = `<input type="text" class="form-control" name="${fieldName}" value="${content}">`;
            }
        }
    });
    
    // 更改操作按钮
    const actionCell = cells[cells.length - 1];
    actionCell.innerHTML = `
        <button class="btn btn-sm btn-success" onclick="saveEdit(${id})">保存</button>
        <button class="btn btn-sm btn-secondary" onclick="cancelEdit(${id})">取消</button>
    `;
}

// 删除确认对话框
function confirmDelete(id, name) {
    if (confirm(`确定要删除项目 "${name}" 吗？此操作不可恢复！`)) {
        deleteProject(id);
    }
}

// 通用数据加载函数
function loadData(url, targetElementId, renderFunction) {
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error('网络响应异常');
            }
            return response.json();
        })
        .then(data => {
            const targetElement = document.getElementById(targetElementId);
            if (targetElement) {
                renderFunction(data, targetElement);
            }
        })
        .catch(error => {
            console.error('加载数据失败:', error);
            alert('数据加载失败，请刷新页面重试');
        });
}