# 更新日志

## v1.2.0

### 变更
- **调价提示只保留调价幅度**：原来的 `tips` 是整段新闻，包含国际原油行情与下次调价窗口，
  现在只截取“经过 N 个工作日统计，油价下调/上调 X 元/吨，即油价上涨/下跌 Y 元/升”这一句，
  方便直接放进仪表盘。趋势与调价时间仍由 `trend`、`time`、`next_adjust_date` 单独提供。
- **新增紧凑版 Lovelace 卡片模板**：`油价卡片模板-紧凑.yaml`，深色圆角面板 + 顶部日期 +
  两行居中彩色油价 + 底部调价信息，涨跌箭头随 `trend` 自动切换。

## v1.1.0（byff Fork）

### 修复
- **HACS 安装失败**：补齐仓库根目录的 `hacs.json`，Marketplace 现在可以正常安装与更新。
- **山西与陕西同时添加导致集成加载失败**：两个地区的中文名会被转成同一个后缀 `shan_xi`，
  第二个地区的实体重命名会抛出 `Entity with this ID is already registered`。
  现在为每个地区固定一个唯一后缀，陕西使用 `shaan_xi`。
- **实体 ID 未按预期生成**：`_attr_object_id` 早已从 Home Assistant 核心中移除，属于无效代码。
  改为覆盖 `suggested_object_id`，实体 ID 现在会真正保持为 `you_jie_<地区>_<字段>`。
- **调价日期少算一天**：`24时` 形式的调价时间会被解析成当天的 0 点，现已按次日 0 点处理，
  并优先采用页面括号内明确写出的时间。
- **部分地区读不到下次调价时间**：新增“下一个油价调整日期为”这一常见措辞。
- **调价提示取到了过期新闻**：现在优先取当天日期的新闻段落，而不是更早日期的旧消息。
- **趋势被国际油价干扰**：排除“国际油价”“原油价格”等原油行情描述，只按国内成品油调价结论判断。
- **无 89# 汽油的省份价格错位**：价格改为按油品标签对应，不再按固定下标取值。
- **新版 Home Assistant 无法保存选项**：`OptionsFlow` 不再给只读属性 `config_entry` 赋值，
  修复 Home Assistant 2025.12 及以上版本打开“配置”时报错的问题。
- 数据源改用 HTTPS。

### 变更
- 集成名称改为「油价」，并补充 HACS 所需的 `hacs.json` 与 `.gitignore`。
- 补齐回归测试，覆盖价格解析、调价时间、趋势判断与实体 ID 唯一性。

## v1.0.1

### 新增
- 全面切换为 UI 配置流程（无需 `configuration.yaml`）。
- 新增“更新周期（小时）”配置：必填数字输入，默认 `12`，范围 `1-168`。
- 新增设备控制按钮：`button.you_jie_<region_slug>_refresh`，点击后立即刷新。
- 新增亮色/深色 Lovelace 模板：`油价卡片模板.yaml`、`油价卡片模板-深色.yaml`。

### 变更
- 传感器模型从“单实体+属性”升级为“多实体状态输出”。
- 油价字段改为独立状态实体（示例：北京）：
  - `sensor.you_jie_bei_jing_gas92`
  - `sensor.you_jie_bei_jing_gas95`
  - `sensor.you_jie_bei_jing_gas98`
  - `sensor.you_jie_bei_jing_die0`
  - `sensor.you_jie_bei_jing_time`
  - `sensor.you_jie_bei_jing_tips`
  - `sensor.you_jie_bei_jing_update_time`
  - `sensor.you_jie_bei_jing_friendly_name`

### 迁移
- 自动清理旧单实体模型，避免和新多实体并存。
- 自动规范按钮实体命名。

### 可能影响（Breaking Changes）
- 旧卡片若读取 `state_attr(sensor.xxx, 'gas92')`，需改为读取独立实体状态（如 `states('sensor.you_jie_bei_jing_gas92')`）。
- 升级后建议重启 Home Assistant 或重载一次本集成以完成迁移。

