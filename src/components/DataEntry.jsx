import React, { useState } from 'react';
import '../styles/DataEntry.css';

function DataEntry() {
  const [formData, setFormData] = useState({
    projectName: '',
    cost: 0
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    // 提交数据逻辑
    console.log('提交数据:', formData);
  };

  return (
    <div className="data-entry-form">
      <h1>数据录入</h1>
      {/* 表单内容 */}
    </div>
  );
}

export default DataEntry;