# Security

## 密钥处理(硬性)

1. **本项目不含任何密钥**。所有 API key / secret / 测试网凭证都在 `.env` 或环境变量中，且已被 `.gitignore` 排除，永不进入 git 历史。
2. 如果你 fork 后添加了自己的密钥：
   - 放在 `.env`(已被忽略)
   - 用 `os.environ.get("KEY")` 读取，**绝不硬编码在代码里**
   - 提交前跑 `git diff --cached | grep -i "key\|secret"` 自查
3. 若误提交了密钥：
   - 立即在服务商后台**撤销**该 key(不是删 commit——历史里的 key 已泄露)
   - 再用 `git filter-branch` / `BFG` 清理历史

## 数据

- 本仓库不含交易账户/持仓/收益数据
- 示例数据为公开行情(Binance Vision / Gate 免费 REST)

## 报告漏洞

- 提交 issue 并标注 [security]
- 或邮件联系维护者(见 README)

## 使用免责

本引擎只做**验证**，不做**交易建议**。任何策略通过验证都不构成"该策略能赚钱"的保证——验证只说明它通过了统计门槛，实盘还需人工监督 + 小额验证 + 可熔断。
