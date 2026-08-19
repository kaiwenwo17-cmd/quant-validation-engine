# 推送 quant-validation-engine 到 GitHub — 完整步骤

> 前提：仓库已在本地 `D:\moxing\quant-validation-engine`，已 commit（58de35b）
> 你的 git 身份：吴文彬 / wbb12258@qq.com（已配置）
> 方式：HTTPS + Personal Access Token（无需安装 gh CLI）

---

## 第 1 步：在 GitHub 创建空仓库

1. 浏览器打开 `https://github.com/new`
2. 填：
   - **Repository name**: `quant-validation-engine`
   - **Description**: `Quant strategy validation engine — four iron laws, zero strategy passed (that's how it works)`
   - **Public**（要共建生态就公开）
   - **不要**勾选 "Add a README" / ".gitignore" / "license"（本地已有，避免冲突）
3. 点 **Create repository**
4. 记下仓库地址（形如 `https://github.com/吴文彬的账号/quant-validation-engine.git`）

## 第 2 步：生成访问令牌（Personal Access Token）

1. 打开 `https://github.com/settings/tokens`
2. 点 **Generate new token** → **Generate new token (classic)**
3. 填：
   - **Note**: `quant-validation-engine push`
   - **Expiration**: 90 days（够了）
   - **Select scopes**: 勾选 **`repo`**（唯一必需项）
4. 点 **Generate token**
5. **立刻复制**令牌（形如 `ghp_xxxxxxxxxxxxxxxx`）——**只显示一次**，关页面就没了
   ⚠️ 令牌=密码，别发给任何人，别提交进任何文件

## 第 3 步：本地推送到 GitHub

打开 PowerShell 或 Git Bash，执行：

```powershell
cd D:\moxing\quant-validation-engine
git remote add origin https://github.com/<你的账号>/quant-validation-engine.git
git push -u origin master
```

推送时会**弹窗要求输入凭据**：
- 用户名：你的 GitHub 账号名
- 密码：**粘贴第 2 步的令牌**（不是你的登录密码！）

> 如果 Git 弹的是浏览器授权窗，直接浏览器里登录即可（GitHub Desktop 已登录的话自动通过）。

## 第 4 步：验证推送成功

浏览器打开 `https://github.com/<你的账号>/quant-validation-engine`

应该看到：
- README.md 渲染（标题 + 四铁律说明 + 架构图）
- 10 个文件：`.gitignore` / `LICENSE` / `README.md` / `SECURITY.md` / `core/four_laws.py` / `examples/rsi_reversal.py` / `strategy_layer/*.py`
- 提交记录 `init: Quant Validation Engine`

## 第 5 步（可选）：本地验证开源引擎可独立运行

```powershell
cd D:\moxing\quant-validation-engine
python -m examples.rsi_reversal
```

预期输出：`★ 判决: REJECT`（RSI 反转被四铁律拒绝——引擎工作正常）

---

## 常见问题

| 问题 | 解决 |
|---|---|
| `remote origin already exists` | `git remote remove origin` 再重来 |
| `Permission denied (publickey)` | 说明走了 SSH——改用 HTTPS 地址（`https://github.com/...`） |
| `Authentication failed` | 用户名填错 或 令牌粘贴错——重新生成令牌 |
| `token 过期` | 90 天后重新生成，重新 push |
| 推完发现传了不该传的 | `.gitignore` 已挡密钥/数据；若真误传，按 SECURITY.md 流程撤销 key + 清历史 |

---

## 之后怎么共建（README 已写好，等人来）

1. **Issue 入口**：别人可以提交新机制模板（30 族只实现了 13 个）、新状态变量、或挑战框架本身
2. **你的联系方式**：想附的话，在 README 末尾加一行 `Maintainer: 吴文彬 (wbb12258@qq.com)`（可选）
3. **Star/PR 都是生态**：有人 star = 框架有共鸣；有人 PR = 真共建开始

---

*推送后如需我帮你写 CONTRIBUTING.md 或首次 release 说明，说一声。*
