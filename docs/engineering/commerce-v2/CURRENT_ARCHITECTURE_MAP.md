# 当前架构图谱

```text
Next.js /commerce (CommerceCenter 单页)
        |
        v
web/lib/api.ts
        |
        v
FastAPI haha_api/main.py /api/commerce/*
        |
        v
CommerceService
  |                  |
  v                  v
CommerceRepository   Identity/CreatorRepository
  |                  (统一账户与角色授权)
  v
SQLAlchemyCommerceRepository
  |
  v
PostgreSQL commerce_* 表 + commerce_events
```

AI 当前只存在于媒体创作和学习老师路径：

```text
Business Service -> haha_media.ModelRouter -> DeepSeek
```

电商尚未接入 Model Router，也不存在商品检索工具、导购会话或推荐证据表。

