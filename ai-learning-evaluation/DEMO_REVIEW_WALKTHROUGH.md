# 两人审核 Demo 演示流程

使用同一台电脑、同一份本地数据库中的两个不同账号，例如 `xinling` 和 `zhu`。Docker 中两个账号需要连接同一个运行中的容器，数据库保存在 shared 卷；不同电脑各自启动的本地数据库不会自动同步。

## 第一人：准备并提交

1. 登录第一个账号，进入 **Report library → My reports**。
2. 选择 **Create report**，导入 CSV/Excel。可用 `data/synthetic_qualtrics_evaluation.csv` 演示。
3. 在 **Themes & evidence** 阅读证据，对每个主题选择 Confirm 或 Reject。
4. 进入 **Report studio**，选择 facilitator 或 client，点击 **Generate draft**。没有配置 Gemini 时可生成本地固定措辞草稿。
5. 在 **Check facts & quotes** 检查所有正文与引用，接受、清除或删除相关内容。直接修改正文后，需要检查新增或改变的内容。
6. **Save draft** 只保存个人进度；首次保存时输入报告名。已有草稿可继续使用。
7. 打开 **Human review / Review & export**，点击 **Submit for review**。如果未保存，会先要求命名；保存或检查失败则不会提交。
8. 成功后显示已提交，正文锁定。右上角选择 **Switch account**。

## 第二人：审核并批准

1. 登录第二个账号，进入 **Report library → Pending review**。
2. 点击 **Review report**。可以查看正文、原始数据的分析结果、主题证据及第一人的检查记录；不能直接改动已提交正文。
3. 点击 **Review decision** 打开审核面板。第一人、第二人的名字自动来自账号。
4. 选择审核角色，勾选证据、隐私和最终措辞确认，再点击 **Approve report**。client 报告须选择 **Learning Futures lead**。
5. 批准先保存到数据库，按钮变为 **Export approved**。点击后选择 Word 或 Markdown 保存位置。
6. 取消导出不会取消批准；文件写入失败也可重试。重新登录后，作者和批准人都可在 **Approved** 中再次打开、导出同一批准版本。

## 退回修改演示

1. 第二人打开另一份待审核报告，选择 **Return for changes** 并填写修改意见。
2. 第一人登录后，在 **My reports** 打开状态为 **Changes requested** 的报告。
3. 在 Human review 中查看完整意见，修改正文；若改变主题，重新生成正文。
4. 检查新增或改变的正文与引用，再次 **Submit for review**。
5. 第二人再次在 Pending review 中打开并批准。最终报告的 Review record 保留退回次数以及提交、批准身份和时间。

## 本版本行为

- 普通草稿仅创建者可见；提交后才进入其他账号的待审核列表。
- 第一人不能批准或退回自己的报告。
- 已提交和已批准正文不可直接编辑；已批准报告暂不提供重新打开编辑功能。
- 同一报告被另一窗口更新后，旧窗口操作会被拒绝，需要重新打开。
- More 中的重命名、删除仅对本人可编辑的草稿显示。
- 审核角色由第二人选择，尚未实现管理员分配角色权限；两个账号用于演示身份分离。
- 数据库自动兼容升级，不需要删除旧草稿。
