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
            })),

            // 付款条件
            advance_payment: document.querySelector('textarea[name="advance_payment"]')?.value || '',
            progress_payment: document.querySelector('textarea[name="progress_payment"]')?.value || '',
            advance_deduction: document.querySelector('textarea[name="advance_deduction"]')?.value || '',
            warranty_amount: document.querySelector('textarea[name="warranty_amount"]')?.value || '',
            completion_payment: document.querySelector('textarea[name="completion_payment"]')?.value || '',
            quality_warranty: document.querySelector('textarea[name="quality_warranty"]')?.value || '',

            // 结算条件
            settlement_condition_1: document.querySelector('textarea[name="settlement_condition_1"]')?.value || '',
            settlement_condition_2: document.querySelector('textarea[name="settlement_condition_2"]')?.value || '',
            settlement_condition_3: document.querySelector('textarea[name="settlement_condition_3"]')?.value || '',
            settlement_condition_4: document.querySelector('textarea[name="settlement_condition_4"]')?.value || '',
            settlement_condition_5: document.querySelector('textarea[name="settlement_condition_5"]')?.value || '',
            settlement_condition_6: document.querySelector('textarea[name="settlement_condition_6"]')?.value || '',

            // 特殊计价原则
            earth_excavation: document.querySelector('textarea[name="earth_excavation"]')?.value || '',
            concrete_engineering: document.querySelector('textarea[name="concrete_engineering"]')?.value || '',
            steel_engineering: document.querySelector('textarea[name="steel_engineering"]')?.value || '',
            formwork_engineering: document.querySelector('textarea[name="formwork_engineering"]')?.value || '',
            masonry_engineering: document.querySelector('textarea[name="masonry_engineering"]')?.value || '',
            waterproof_engineering: document.querySelector('textarea[name="waterproof_engineering"]')?.value || '',
            external_wall_waterproof: document.querySelector('textarea[name="external_wall_waterproof"]')?.value || '',

            // 措施费说明
            total_measures: document.querySelector('textarea[name="total_measures"]')?.value || '',
            template_engineering: document.querySelector('textarea[name="template_engineering"]')?.value || '',
            scaffolding_engineering: document.querySelector('textarea[name="scaffolding_engineering"]')?.value || '',
            seasonal_measures: document.querySelector('textarea[name="seasonal_measures"]')?.value || '',
            vertical_transport: document.querySelector('textarea[name="vertical_transport"]')?.value || '',
            dewatering_measures: document.querySelector('textarea[name="dewatering_measures"]')?.value || '',
            special_measures: document.querySelector('textarea[name="special_measures"]')?.value || '',

            // 三、变更签证管理
            // 1. 变更签证程序
            change_procedure: {
                initiating_department: document.querySelector('textarea[name="initiating_department"]')?.value || '',
                approval_points: document.querySelector('textarea[name="approval_points"]')?.value || '',
                instruction_issue: document.querySelector('textarea[name="instruction_issue"]')?.value || '',
                completion_confirmation: document.querySelector('textarea[name="completion_confirmation"]')?.value || '',
                cost_declaration: document.querySelector('textarea[name="cost_declaration"]')?.value || '',
                cost_approval: document.querySelector('textarea[name="cost_approval"]')?.value || ''
            },

            // 2. 变更成本控制
            change_cost_control: document.querySelector('textarea[name="change_cost_control"]')?.value || '',

            // 四、清单和合同中需注意的特殊计价原则
            pricing_principles: {
                earth_excavation: document.querySelector('input[name="earth_excavation"]')?.value || '',
                rock_excavation: document.querySelector('input[name="rock_excavation"]')?.value || '',
                backfill: document.querySelector('input[name="backfill"]')?.value || '',
                static_blasting: document.querySelector('input[name="static_blasting"]')?.value || '',
                pile_rock_penetration: document.querySelector('input[name="pile_rock_penetration"]')?.value || '',
                rock_recovery: document.querySelector('input[name="rock_recovery"]')?.value || '',
                soil_transport: document.querySelector('input[name="soil_transport"]')?.value || '',
                rock_transport: document.querySelector('input[name="rock_transport"]')?.value || '',
                muck_truck: document.querySelector('input[name="muck_truck"]')?.value || '',
                earthwork_confirmation: document.querySelector('input[name="earthwork_confirmation"]')?.value || '',
                basement_waterproof: document.querySelector('input[name="basement_waterproof"]')?.value || '',
                external_wall_waterproof: document.querySelector('input[name="external_wall_waterproof"]')?.value || '',
                glass_curtain_wall: document.querySelector('input[name="glass_curtain_wall"]')?.value || '',
                floor_leveling: document.querySelector('input[name="floor_leveling"]')?.value || '',
                demolition: document.querySelector('input[name="demolition"]')?.value || '',
                pile_filling_coefficient: document.querySelector('input[name="pile_filling_coefficient"]')?.value || '',
                temp_equipment_disposal: document.querySelector('input[name="temp_equipment_disposal"]')?.value || ''
            },

            // 五、材料品牌的约定及选取原则
            material_principles: {
                // 1. 材料品牌选用原则
                brand_selection: {
                    // 选用范围（复选框）
                    company_brand: document.querySelector('input[name="company_brand"]')?.checked || false,
                    district_brand: document.querySelector('input[name="district_brand"]')?.checked || false,
                    city_brand: document.querySelector('input[name="city_brand"]')?.checked || false,
                    top30_brand: document.querySelector('input[name="top30_brand"]')?.checked || false,
                    other_brand: document.querySelector('input[name="other_brand"]')?.checked || false,
                    // 档次
                    brand_level: document.querySelector('input[name="grade_level"]')?.value || ''
                },
                // 2. 材料品牌确认程序
                in_library_confirmation: document.querySelector('textarea[name="in_library_confirmation"]')?.value || '',
                out_library_confirmation: document.querySelector('textarea[name="out_library_confirmation"]')?.value || ''
            },

            // 六、发包人工作中需要注意的事项
            employer_notes: document.querySelector('textarea[name="employer_notes"]')?.value || '',
            work_requirements: document.querySelector('textarea[name="work_requirements"]')?.value || '',
            special_requirements: document.querySelector('textarea[name="special_requirements"]')?.value || '',

            // 七、措施费的有关特殊情况说明
            total_measures: document.querySelector('textarea[name="total_measures"]')?.value || '',
            template_engineering: document.querySelector('textarea[name="template_engineering"]')?.value || '',
            scaffolding_engineering: document.querySelector('textarea[name="scaffolding_engineering"]')?.value || '',
            seasonal_measures: document.querySelector('textarea[name="seasonal_measures"]')?.value || '',
            vertical_transport: document.querySelector('textarea[name="vertical_transport"]')?.value || '',
            dewatering_measures: document.querySelector('textarea[name="dewatering_measures"]')?.value || '',
            special_measures: document.querySelector('textarea[name="special_measures"]')?.value || '',
            measure_notes: document.querySelector('textarea[name="measure_notes"]')?.value || ''
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
