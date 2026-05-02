# 重要：前端 v3 连接后端前必须打这个补丁

`novel-studio-pro-frontend-v3` 的原始 `src/api.js` 在 Mock 模式下会更新前端本地状态；但关闭 Mock 连接真实后端时，只返回接口结果，没有把后端返回的 project / chapter 写入前端状态。

所以如果不打补丁，会出现：

```text
后端接口成功了，但前端页面没有变化。
```

## Trae 必须做的事

把本后端包里的文件：

```text
frontend_patch/api.js
```

复制并覆盖到前端项目：

```text
novel-studio-pro-frontend-v3/src/api.js
```

然后重新运行前端：

```bash
npm run dev
```

这样前端在关闭 Mock 模式后，才能正确：

```text
创建项目后写入项目列表
构建蓝图后刷新故事蓝图
生成下一章后显示 pendingChapter
确认章节后更新项目状态、事件账本、伏笔和角色状态
```
