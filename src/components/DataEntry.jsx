<div className="data-entry-container">
  <h1 className="form-title">数据录入</h1>
  
  <label className="input-label">
    <input 
      className="input-field"
    />
  </label>
  
  <button 
    className="submit-button"
  >
    提交
  </button>
  
  {error && <div className="error-message">{error}</div>}
  {success && <div className="success-message">{success}</div>}
</div> 