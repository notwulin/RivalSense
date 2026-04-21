# 分析引擎

分析引擎采用 Local-First 设计：本地 NLP 先完成统计、过滤、聚类和证据压缩，大模型只负责最后的高层总结。这样可以降低 token 成本，也能减少无关长文本进入 LLM。

## 处理入口

主入口：`services/data_analyzer.py`

```text
process_and_summarize(competitor_name, crawled_data)
  -> statistical_summary
  -> analytics
```

`services/ai_analyzer.py` 使用 `statistical_summary` 生成报告。如果 AI 未配置或调用失败，会使用本地兜底分析。

## 情感分析

- 英文：NLTK VADER。
- 中文：SnowNLP。
- 分数范围：`-1.0` 到 `1.0`。
- 默认阈值：
  - `< -0.15`：negative
  - `> 0.15`：positive
  - 其他：neutral

抓取层的 `mixed` 会在分析层转为 negative，避免带有抱怨的混合评论被误删。

## 痛点聚类

流程：

1. 从抓取记录中筛选痛点候选。
2. 归一化常见问题短语，例如 `not working`、`feature request`、`price increase`。
3. 英文用正则 token，中文用 jieba 分词。
4. 使用英文停用词、自定义停用词、低信息词和竞品名词做过滤。
5. TF-IDF 提取 unigram/bigram/trigram。
6. KMeans 聚类。
7. 根据关键词映射痛点分类。

已显式过滤的低信息词包括：

```text
they, one, get, still, anyone, like, me, apple, google, microsoft
```

这类词不会再作为痛点关键词输出。若后续又出现类似弱相关词，应优先加到 `CUSTOM_STOPWORDS` 或 `LOW_INFORMATION_TOKENS`，并检查上游去噪是否放入了弱相关语料。

## 痛点分类

当前分类规则：

- 稳定性与故障
- 性能与响应速度
- 价格与订阅成本
- 功能缺口与集成
- 易用性与界面复杂度
- 账号与登录
- 客服与退款
- 隐私与安全

未命中规则时，会回退为 `围绕 <keyword> 的集中抱怨`。

## 商业信号

`identify_business_signals(records)` 扫描：

- 融资动态
- 定价变动
- 产品发布
- 人才变动
- 法务监管
- 安全事故

商业信号来自规则匹配。它适合做高召回雷达，不应直接当作最终事实；报告层需要保留来源标题、URL 和原文证据。

## Analytics 输出

`analytics` 用于前端可视化：

```json
{
  "total_records": 120,
  "source_distribution": {},
  "sentiment_distribution": {},
  "sentiment_percentages": {},
  "avg_negative_score": -0.42,
  "pain_clusters": [],
  "business_signals": [],
  "top_negative_quotes": []
}
```

`pain_clusters` 中每个簇包含：

- `cluster_label`
- `count`
- `keywords`
- `sample_quote`
- `source_breakdown`

## 评估建议

每次改动分析引擎后，至少人工检查：

- Top 5 痛点簇关键词是否能表达真实问题。
- 是否出现 they/one/get/like 等低信息词。
- sample quote 是否和 cluster_label 对得上。
- 商业信号是否误把普通新闻当重大事件。
- 正面评论是否被误判成痛点。

建议增加一个小型 gold set：

- 每条样本标注 competitor、source、intent、是否相关、痛点类别。
- 用脚本统计 precision、recall、低信息关键词比例。
