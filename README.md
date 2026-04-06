# 中检数据治理平台 API 测试程序

## 功能说明

基于Python的中检数据治理平台API测试程序，支持：

1. 每个模块独立的测试程序
2. 统一的签名认证机制
3. 共享配置文件管理
4. 格式化的响应数据输出
5. 支持单个模块测试或全部模块测试

## 环境要求

- Python 3.8+
- 依赖包: requests

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置文件

编辑 `config/api_config.ini` 文件，配置服务器地址和认证信息：

```ini
[server]
host = http://your-server:port
timeout = 10

[auth]
app_key = your-app-key
app_secret = your-app-secret

[test]
verbose = true
save_response = true
response_dir = responses
```

## 使用方法

### 运行所有模块测试

```bash
python run_all_tests.py
```

### 运行指定模块测试

```bash
python run_all_tests.py -m overview upss udmds
```

### 运行单个模块测试

```bash
# 系统概览模块
python test_cases/test_overview.py

# 沉降感知模块
python test_cases/test_upss.py
```

### 列出所有可用模块

```bash
python run_all_tests.py --list
```

## 项目结构

```
test/
├── config/                    # 配置文件
│   ├── config.py             # 配置加载模块
│   └── api_config.ini        # API配置文件
├── lib/                      # 共享库
│   ├── signature.py          # 签名工具
│   ├── api_client.py         # API客户端
│   └── response_printer.py   # 响应打印工具
├── test_cases/              # 测试用例
│   ├── test_overview.py     # 系统概览测试
│   ├── test_upss.py         # 沉降感知测试
│   └── ...
├── run_all_tests.py         # 主测试程序
├── requirements.txt         # 依赖列表
└── README.md               # 使用说明
```

## 测试模块列表

| 模块代码 | 模块名称 | 接口数量 |
|---------|---------|---------|
| overview | 系统概览 | 2 |
| unga | 走航甲烷检测 | 5 |
| gnss-device | 北斗设备状态 | 3 |
| upns | 短临降水预警 | 9 |
| ugss | GNSS干扰监测 | 7 |
| udmds | 形变安全监测 | 7 |
| upss | 沉降态势感知 | 11 |

## 注意事项

1. 首次运行前请确保配置 `api_config.ini` 中的服务器地址和认证信息
2. 测试程序会打印详细的响应数据，可通过配置文件关闭
3. 响应数据可选择保存到文件，便于后续分析
4. 每个测试程序都可以独立运行，也可以通过主程序批量运行
