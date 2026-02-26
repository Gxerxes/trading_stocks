# 双模式分析系统 - 更新说明

## 📋 概述

支持两种分析模式的完整更新，使 OpenAI API 成为可选项，用户可以选择：
- **本地分析模式**：完全免费，无需 API Key，基于规则的评分系统
- **API 分析模式**：使用 OpenAI 进行智能分析，需要 API Key

---

## 🔄 更新的文件清单

### 1. 核心配置文件

#### `ai_stock_agent/config/settings.py`
- ✅ 新增 `ANALYSIS_MODE` 环境变量（默认："local"）
- ✅ 更新 `validate_config()` 使 OpenAI API Key 仅在 API 模式下需要
- ✅ 添加了配置说明注释

#### `ai_stock_agent/agent/local_analyzer.py`
- ✅ **新增文件**（300+ 行）
- ✅ 完整的规则基础分析实现
- 核心方法：
  - `_evaluate_trend()` - 趋势评分（40%权重）
  - `_evaluate_volume()` - 量价配合评分（30%权重）
  - `_evaluate_technical()` - 技术面评分（30%权重）
  - `_generate_signal()` - 信号生成（BUY/WATCH/SELL）
  - `_calculate_entry_price()` - 建议入场价
  - `_calculate_stop_loss()` - 止损价格
  - `_calculate_target_price()` - 目标价格
  - `_generate_reason()` - 分析理由
  - `analyze_batch()` - 批量处理

#### `ai_stock_agent/agent/llm_agent.py`
- ✅ 修改 `__init__()` 适应可选 API Key
- ✅ 修改 `analyze_stock()` 无法调用 API 时的降级处理
- ✅ 保持与本地分析器相同的返回格式

### 2. 主程序更新

#### `ai_stock_agent/main.py`
- ✅ 导入 `LocalAnalyzer` 和 `ANALYSIS_MODE`
- ✅ 更新分析逻辑：根据 `ANALYSIS_MODE` 选择使用哪个分析器
- ✅ 条件语句：
  ```python
  if ANALYSIS_MODE.lower() == "api":
      analyzer = LLMAgent()
  else:
      analyzer = LocalAnalyzer()
  ```

### 3. 启动脚本更新

#### `run.sh`
- ✅ 智能化的 API Key 检查
- ✅ 根据 `ANALYSIS_MODE` 决定是否需要 OpenAI API Key
- ✅ 更新错误提示信息

#### `example_usage.py`
- ✅ 导入 `ANALYSIS_MODE` 和 `LocalAnalyzer`
- ✅ 更新示例函数支持两种分析模式
- ✅ 改进的配置检查逻辑

#### `check_config.py`
- ✅ 导入 `ANALYSIS_MODE`
- ✅ 更新 `check_env_vars()` 根据分析模式检查配置
- ✅ 更新 `check_dependencies()` 条件检查 openai 包

#### `test_features.py`
- ✅ 移除强制的 OpenAI API Key 检查
- ✅ 只要求 Tushare Token（特征测试不需要分析）

### 4. 配置文件更新

#### `.env.example`
- ✅ 新增 `ANALYSIS_MODE` 作为主配置
- ✅ 明确标注 OpenAI 配置仅在 API 模式需要
- ✅ 更清晰的配置说明

### 5. 文档更新

#### `README.md`
- ✅ 新增分析模式对比表格
- ✅ 扩展工作流程图表示模式分支
- ✅ 详细讲解两种分析模式实现
- ✅ 扩展 FAQ 部分（新增 6+ 问答）
- ✅ 成本分析和精度对比

#### `QUICKSTART.md`
- ✅ 重构快速开始部分，模式选择优先级高
- ✅ 分离本地模式和 API 模式的配置步骤
- ✅ 更新核心功能说明，展示两种分析器
- ✅ 添加模式对比表格
- ✅ 新增 6+ 问答项关于模式选择和切换

---

## 🎯 关键特性

### 本地分析模式 (ANALYSIS_MODE=local)

**优势：**
- ✅ 完全免费，无需任何付费 API
- ✅ 无网络依赖，本地快速处理
- ✅ 支持自定义权重和规则
- ✅ 开箱即用，无需额外配置

**实现：**
- 四分量评分系统（0-100）：
  - 趋势强度（40%）：MA 交叉、价格动量、形态
  - 量价配合（30%）：成交量比、价量同步
  - 技术面（30%）：价格定位、MA 间距
- 信号判定：BUY ≥70 | WATCH 40-70 | SELL <40
- 动态计算入场价、止损价、目标价

### API 分析模式 (ANALYSIS_MODE=api)

**优势：**
- ✅ 使用 GPT 进行智能分析，精度更高
- ✅ 支持多模型选择（gpt-3.5-turbo 到 gpt-4）
- ✅ 更灵活的分析逻辑和自适应能力

**成本参考：**
- gpt-3.5-turbo: ¥2-3/天（推荐）
- gpt-4: ¥15-30/天

---

## 🚀 使用指南

### 快速开始（本地模式 - 推荐）

```bash
# 1. 配置 .env
TUSHARE_TOKEN=your_token
ANALYSIS_MODE=local

# 2. 运行
python ai_stock_agent/main.py
```

### 切换到 API 模式

```bash
# 1. 配置 .env
TUSHARE_TOKEN=your_token
ANALYSIS_MODE=api
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4

# 2. 运行
python ai_stock_agent/main.py
```

### 随时切换模式

只需修改 .env 中的 `ANALYSIS_MODE` 值即可，无需重启应用。

---

## ✨ 返回数据格式统一

两种模式返回完全相同的信号格式：

```python
{
    "symbol": "000001.SZ",          # 股票代码
    "signal": "BUY",                # 信号：BUY/WATCH/SELL
    "score": 75,                    # 评分：0-100
    "confidence": 85,               # 信心度：0-100
    "entry_price": 10.50,           # 建议入场价
    "stop_loss": 9.80,              # 止损价格
    "target_price": 12.00,          # 目标价格
    "reason": "趋势向上，量价配合"   # 分析理由
}
```

---

## 🔧 故障排除

### 问题：本地模式运行缓慢

**解决：** 这是正常的。本地分析是计算密集型的。如需加速，考虑：
- 减少股票池大小
- 使用 API 模式（更快）

### 问题：两种模式的结果不同

**解决：** 完全正常：
- 本地模式：基于固定规则
- API 模式：基于 LLM 动态分析

这种差异可用于交叉验证和模型改进。

### 问题：如何比较两种模式？

**建议：**
```python
# 同时运行两种分析
ANALYSIS_MODE=local  # 运行获取本地结果
ANALYSIS_MODE=api    # 运行获取 API 结果
# 对比两组结果进行分析
```

---

## 📊 测试建议

1. **功能测试**
   ```bash
   python test_features.py  # 数据层测试
   python check_config.py   # 配置验证
   ```

2. **模式测试**
   ```bash
   ANALYSIS_MODE=local python ai_stock_agent/main.py
   ANALYSIS_MODE=api python ai_stock_agent/main.py
   # 对比两个输出
   ```

3. **性能测试**
   - 测试 50 只股票的处理时间
   - 本地模式 vs API 模式

---

## 📝 更新检查清单

- [x] 配置系统支持 ANALYSIS_MODE
- [x] LocalAnalyzer 完整实现
- [x] LLMAgent 可选 API 支持
- [x] Main.py 支持两种分析器
- [x] 启动脚本智能化配置检查
- [x] 环境变量示例文档化
- [x] README 更新说明
- [x] QUICKSTART 快速入门
- [x] 示例代码展示两种用法
- [x] 依赖检查脚本更新
- [x] 错误提示和文档完整

---

## 🎓 学习资源

### LocalAnalyzer 实现细节

参考文件：[ai_stock_agent/agent/local_analyzer.py](ai_stock_agent/agent/local_analyzer.py)

### API 模式实现

参考文件：[ai_stock_agent/agent/llm_agent.py](ai_stock_agent/agent/llm_agent.py)

### 使用示例

参考文件：[example_usage.py](example_usage.py)

---

## 🤝 反馈和改进

- 双模式对比数据可用于模型优化
- LocalAnalyzer 权重可按需调整
- API 模式可尝试不同模型
- 欢迎提交改进建议

---

**更新日期**: 2024  
**版本**: 2.0 (双模式支持)  
**状态**: ✅ 完成并测试
